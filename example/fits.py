"""
An example of building the database for a simple array.

Two modes: create database, and visualize database.
"""

import sys

import numpy as np

import tilemaker.database as db
import tilemaker.orm
from tilemaker.processing.fits_simple import FITSSimpleLoader, FITSFile, LayerTree

QUANTITY_MAP = {
    "uK": "T",
}

mode = sys.argv[1]

if mode == "create":
    db.create_database_and_tables()

    filename = sys.argv[2]
    map_name = sys.argv[3]
    fits_file = FITSFile(filename=filename)

    with db.get_session() as session:
        add = []
        
        if (map_metadata := session.get(tilemaker.orm.Map, map_name)) is None:
            map_metadata = tilemaker.orm.Map(
                name=map_name,
                description="An example fits map",
                telescope=fits_file.individual_trees[0].header.get("TELESCOP", None),
                data_release=fits_file.individual_trees[0].header.get("RELEASE", None),
                season=fits_file.individual_trees[0].header.get("SEASON", None),
                tags=fits_file.individual_trees[0].header.get("ACTTAGS", None),
                patch=fits_file.individual_trees[0].header.get("PATCH", None)
            )

            add.append(map_metadata)

        for fits_image in fits_file.individual_trees:
            tile_size = fits_image.tile_size
            number_of_layers = fits_image.number_of_levels

            tree = LayerTree(number_of_layers=number_of_layers, image_pixel_size=tile_size, image=fits_image)

            top_right, bottom_left = fits_image.world_size_degrees()

            band = tilemaker.orm.Band(
                map=map_metadata,
                tiles_available=True,
                levels=number_of_layers,
                tile_size=tile_size,
                frequency=str(fits_image.header.get("FREQ", "").replace("f", "90")),
                stokes_parameter=str(fits_image.identifier),
                units=str(fits_image.header.get("BUNIT", "")),
                recommended_cmap_min=-500.0,
                recommended_cmap_max=500.0,
                recommended_cmap="RdBu_r",
                bounding_left=bottom_left[0].value,
                bounding_right=top_right[0].value,
                bounding_top=top_right[1].value,
                bounding_bottom=bottom_left[1].value,
                quantity=QUANTITY_MAP.get(str(fits_image.header.get("BUNIT", "")), None)
            )

            H, edges = fits_image.histogram_raw_data(
                n_bins=128, min=-2000.0, max=2000.0
            )

            histogram = tilemaker.orm.Histogram(
                band=band,
                start=-2000.0,
                end=2000.0,
                bins=128,
                edges_data_type=str(edges.dtype),
                edges=edges.tobytes(order="C"),
                histogram_data_type=str(H.dtype),
                histogram=H.tobytes(order="C")
            )

            tile_metadata = []

            for depth in range(number_of_layers):
                n_tiles_x = 2 ** (depth + 1)
                n_tiles_y = 2 ** (depth)

                for x in range(n_tiles_x):
                    for y in range(n_tiles_y):
                        tile_data = tree.get_tile(depth, x, y)

                        if isinstance(tile_data.data, np.ma.MaskedArray):
                            bytes = tile_data.data.tobytes(order="C", fill_value=np.NaN)
                        elif tile_data.data is None:
                            bytes = None
                        else:
                            bytes = tile_data.data.tobytes(order="C")

                        tile_metadata.append(tilemaker.orm.Tile(
                            level=depth,
                            x=x,
                            y=y,
                            band=band,
                            data=bytes,
                            data_type=str(tile_data.data.dtype) if tile_data.data is not None else None
                        ))

            add += [band, histogram] + tile_metadata

            session.add_all(add)
            session.commit()

            add = []

    print("Database successfully created.")
elif mode == "delete":
    # Check that we can delete our map easily.
    with db.get_session() as session:
        session.delete(session.get(tilemaker.orm.Map, sys.argv[2]))
        session.commit()

    print("Database successfully deleted.")
else:
    # Visualize the database.
    import matplotlib.pyplot as plt

    # Metadata
    with db.get_session() as session:
        map_metadata = session.get(tilemaker.orm.Map, "FITS_Map")
        band = map_metadata.bands[0]

        # Create a figure with a sub-plot for each level.
        view_levels = band.levels
        #
        fig, axs = plt.subplots(view_levels, 1, figsize=(10, 4 * (view_levels)))

        for level in range(view_levels):
            tiles = session.query(tilemaker.orm.Tile).filter(
                tilemaker.orm.Tile.level == level,
                tilemaker.orm.Tile.band_id == band.id
            ).all()

            # Create a 2D array to hold the tiles. We know the size of
            # this array also from the metadata.
            n_tiles_x = 2 ** (level + 1)
            n_tiles_y = 2 ** (level)

            tile_array = np.empty((n_tiles_y * band.tile_size, n_tiles_x * band.tile_size), order="C")
            tile_array[:] = np.NaN

            for tile in tiles:
                x_range = np.s_[tile.x * band.tile_size:(tile.x + 1) * band.tile_size]
                y_range = np.s_[tile.y * band.tile_size:(tile.y + 1) * band.tile_size]
                x = tile.x
                y = tile.y
                if tile.data is not None:
                    tile_data = np.frombuffer(tile.data, dtype=np.float32).reshape(band.tile_size, band.tile_size)
                    tile_array[y_range, x_range] = tile_data

            axs[level].imshow(tile_array, cmap="viridis", vmin=-500, vmax=500)
            axs[level].set_title(f"Level {level}")

        plt.savefig("comparison.png")

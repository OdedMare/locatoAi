"""Build enriched result rows for proximity operations."""

from shapely.geometry import mapping


class ProximityResultBuilder:
    DISTANCE_COLUMN = "distance_to_target_m"
    MATCH_REASON_COLUMN = "match_reason"
    NEAREST_TARGET_COLUMN = "nearest_target_feature"

    def build(self, gdf, target, nearest_rows, requested_distance=None):
        result = gdf.loc[nearest_rows.index].copy()
        distances = nearest_rows[self.DISTANCE_COLUMN]
        result[self.DISTANCE_COLUMN] = distances
        result[self.MATCH_REASON_COLUMN] = self._reasons(
            distances, requested_distance
        )
        result[self.NEAREST_TARGET_COLUMN] = [
            self._feature(target.loc[index])
            for index in nearest_rows["index_right"]
        ]
        return result

    @staticmethod
    def _reasons(distances, requested_distance):
        if requested_distance is None:
            return [
                "נבחר כאחת הישויות הקרובות ביותר; המרחק מישות הייחוס הוא "
                f"{round(float(distance))} מ׳."
                for distance in distances
            ]
        return [
            f"נמצא במרחק {round(float(distance))} מ׳ מישות הייחוס "
            f"(בטווח המבוקש: {round(float(requested_distance))} מ׳)."
            for distance in distances
        ]

    @staticmethod
    def _feature(row) -> dict:
        properties = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in row.items()
            if key != "geometry"
        }
        return {
            "type": "Feature",
            "geometry": mapping(row.geometry),
            "properties": properties,
        }

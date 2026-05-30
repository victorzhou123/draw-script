from sqlalchemy import select


async def load_project_markers(project_id: str, client_id: str, session_factory) -> dict:
    """Load this client's captured coordinates for all markers in the project.

    Returns {marker_name: {x, y, w, h, window_title, window_process, window_x, window_y}}
    Only includes markers that this specific client has annotated.
    Coordinates are relative to the bound window; client applies live window offset.
    """
    from database import Marker, MarkerCapture
    async with session_factory() as session:
        result = await session.execute(
            select(Marker, MarkerCapture)
            .join(
                MarkerCapture,
                (MarkerCapture.marker_id == Marker.id) & (MarkerCapture.client_id == client_id),
            )
            .where(Marker.project_id == project_id)
        )
        return {
            marker.name: {
                "x": capture.x,
                "y": capture.y,
                "w": capture.w,
                "h": capture.h,
                "window_title": capture.window_title,
                "window_process": capture.window_process,
                "window_x": capture.window_x or 0,
                "window_y": capture.window_y or 0,
            }
            for marker, capture in result.all()
        }

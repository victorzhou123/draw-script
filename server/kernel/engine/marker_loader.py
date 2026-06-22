from sqlalchemy import select


async def load_project_markers(project_id: str, client_id: str, session_factory) -> dict:
    """Load this client's captured coordinates for all markers in the project.

    Returns {marker_name: {x, y, w, h, window_title, window_process, window_x, window_y}}
    Only includes markers that this specific client has annotated.
    Coordinates are relative to the bound window; client applies live window offset.

    Window binding is read from project_client_windows (canonical source) so that
    copied captures and post-migration captures work correctly even though
    marker_captures.window_* is no longer written by new annotations.
    """
    from database import Marker, MarkerCapture, ProjectClientWindow
    async with session_factory() as session:
        pcw = await session.get(ProjectClientWindow, (project_id, client_id))

        result = await session.execute(
            select(Marker, MarkerCapture)
            .join(
                MarkerCapture,
                (MarkerCapture.marker_id == Marker.id) & (MarkerCapture.client_id == client_id),
            )
            .where(Marker.project_id == project_id)
        )

        window_title   = pcw.window_title   if pcw else None
        window_process = pcw.window_process if pcw else None
        window_x       = (pcw.window_x or 0) if pcw else 0
        window_y       = (pcw.window_y or 0) if pcw else 0

        return {
            marker.name: {
                "x": capture.x,
                "y": capture.y,
                "w": capture.w,
                "h": capture.h,
                "window_title":   window_title,
                "window_process": window_process,
                "window_x":       window_x,
                "window_y":       window_y,
            }
            for marker, capture in result.all()
        }

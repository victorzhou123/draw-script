from sqlalchemy import select


async def load_project_markers(project_id: str, client_id: str, session_factory) -> dict:
    """Load this client's captured coordinates for all markers in the project.

    Returns {marker_name: {x, y, w, h, window_title, window_process, window_x, window_y}}
    x/y/w/h are scaled from capture.window_w/h to the current PCW window size so the
    caller always receives values valid for the client's current window dimensions.
    """
    from database import Marker, MarkerCapture, ProjectClientWindow
    async with session_factory() as session:
        result = await session.execute(
            select(Marker, MarkerCapture, ProjectClientWindow)
            .join(
                MarkerCapture,
                (MarkerCapture.marker_id == Marker.id) & (MarkerCapture.client_id == client_id),
            )
            .outerjoin(ProjectClientWindow, MarkerCapture.client_window_id == ProjectClientWindow.id)
            .where(Marker.project_id == project_id)
        )

        markers = {}
        for marker, capture, pcw in result.all():
            cur_w    = pcw.window_w if pcw else None
            cur_h    = pcw.window_h if pcw else None
            window_x = (pcw.window_x or 0) if pcw else 0
            window_y = (pcw.window_y or 0) if pcw else 0

            cap_w, cap_h = capture.window_w, capture.window_h
            if cap_w and cap_h and cur_w and cur_h:
                sx, sy = cur_w / cap_w, cur_h / cap_h
            else:
                sx = sy = 1.0

            markers[marker.name] = {
                "x": round(capture.x * sx) if capture.x is not None else None,
                "y": round(capture.y * sy) if capture.y is not None else None,
                "w": round(capture.w * sx) if capture.w is not None else None,
                "h": round(capture.h * sy) if capture.h is not None else None,
                "window_title":   pcw.window_title   if pcw else None,
                "window_process": pcw.window_process if pcw else None,
                "window_x":       window_x,
                "window_y":       window_y,
            }
        return markers

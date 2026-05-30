from sqlalchemy import select


async def load_project_markers(project_id: str, session_factory) -> dict:
    """Load all captured markers for a project from DB.

    Returns {name: {x, y, w, h, window_title, window_process, window_x, window_y}}
    Only includes markers that have been annotated (x is not None).
    """
    from database import Marker
    async with session_factory() as session:
        result = await session.execute(
            select(Marker).where(
                Marker.project_id == project_id,
                Marker.x.isnot(None),
            )
        )
        return {
            m.name: {
                "x": m.x,
                "y": m.y,
                "w": m.w,
                "h": m.h,
                "window_title": m.window_title,
                "window_process": m.window_process,
                "window_x": m.window_x or 0,
                "window_y": m.window_y or 0,
            }
            for m in result.scalars().all()
        }

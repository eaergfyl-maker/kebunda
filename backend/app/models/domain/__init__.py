"""Core domain entities, re-exported from the engines that own them.

    Climate, FieldContext   one field's weather, soil and management (rotation_engine.context)
    Phase, Schedule         crops placed on the calendar (rotation_engine.schedule)
"""
from app.services.rotation_engine.context import Climate, FieldContext
from app.services.rotation_engine.schedule import Phase, Schedule

__all__ = ["Climate", "FieldContext", "Phase", "Schedule"]

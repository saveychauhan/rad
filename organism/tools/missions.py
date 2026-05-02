from datetime import timedelta
from django.db import models
from organism.models import RadTask
from .utils import broadcast_status_event

async def add_task(title, scheduled_for, priority="medium", description="", created_by="rad", is_recurring=False, recurrence_interval="none"):
    """
    Assigns a new mission to Rad's backlog. 
    MANDATORY: scheduled_for (str: ISO format like '2025-12-31 14:00')
    Args: title (str), priority (str: high/medium/low), is_recurring (bool), recurrence_interval (str: daily/weekly/monthly)
    """
    from django.utils.dateparse import parse_datetime
    
    if not scheduled_for:
        return "ERROR: 'scheduled_for' is mandatory. Please provide a date and time."

    sched_dt = None
    if isinstance(scheduled_for, str):
        sched_dt = parse_datetime(scheduled_for)
    else:
        sched_dt = scheduled_for

    if not sched_dt:
        return f"ERROR: Invalid date format for '{scheduled_for}'. Use YYYY-MM-DD HH:MM."

    task = await RadTask.objects.acreate(
        title=title,
        priority=priority,
        description=description,
        created_by=created_by,
        scheduled_for=sched_dt,
        is_recurring=is_recurring,
        recurrence_interval=recurrence_interval
    )
    return f"NEW MISSION REGISTERED: '{task.title}' [ID: {task.id}]. Scheduled for: {task.scheduled_for.strftime('%Y-%m-%d %H:%M')}."

async def list_tasks():
    """Lists all active and completed tasks with status icons."""
    tasks = RadTask.objects.all().order_by('-priority', 'created_at')
    count = await tasks.acount()
    if count == 0:
        return "BACKLOG EMPTY: No active missions."
    
    res = "--- RAD MISSION LOG ---\n"
    async for t in tasks:
        status_icon = "✅" if t.status == 'done' else ("⏳" if t.status == 'doing' else "📌")
        recurring_icon = " 🔄" if t.is_recurring else ""
        creator_tag = " [BY SAWAN]" if t.created_by == 'sawan' else ""
        sched_tag = f" (Next: {t.scheduled_for.strftime('%Y-%m-%d %H:%M')})" if t.scheduled_for else ""
        res += f"{status_icon}{recurring_icon} [{t.priority.upper()}]{creator_tag} {t.title} - {t.status}{sched_tag}\n"
    return res

async def update_task(task_id_or_title, title=None, priority=None, description=None, status=None, scheduled_for=None, created_by=None):
    """Updates an existing task's fields."""
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone

    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."

    changed = []
    if title is not None:
        task.title = title
        changed.append("title")
    if priority is not None:
        task.priority = priority
        changed.append("priority")
    if description is not None:
        task.description = description
        changed.append("description")
    if status is not None:
        task.status = status
        if status == 'done':
            task.completed_at = timezone.now()
            task.reward_earned = True
        changed.append("status")
    if scheduled_for is not None:
        task.scheduled_for = parse_datetime(scheduled_for)
        changed.append("scheduled_for")
    if created_by is not None:
        task.created_by = created_by
        changed.append("created_by")

    await task.asave()
    return f"MISSION UPDATED: '{task.title}' fields modified: {', '.join(changed)}."

async def complete_task(task_id_or_title):
    """Marks a task as completed. If recurring, schedules the next cycle."""
    from django.utils import timezone
    
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    
    if task.is_recurring:
        now = timezone.now()
        if task.recurrence_interval == 'daily':
            task.scheduled_for = now + timedelta(days=1)
        elif task.recurrence_interval == 'weekly':
            task.scheduled_for = now + timedelta(weeks=1)
        elif task.recurrence_interval == 'monthly':
            task.scheduled_for = now + timedelta(days=30)
        
        task.status = 'todo'
        task.completed_at = now
        await task.asave()
        await broadcast_status_event("task_update_event", {})
        return f"RECURRING MISSION RESET: '{task.title}' rescheduled for {task.scheduled_for.strftime('%Y-%m-%d %H:%M')}."
    else:
        task.status = 'done'
        task.completed_at = timezone.now()
        task.reward_earned = True
        await task.asave()
        await broadcast_status_event("task_update_event", {})
        return f"MISSION ACCOMPLISHED: '{task.title}' is finalized."

async def delete_task(task_id_or_title):
    """Permanently deletes a single task."""
    task = await RadTask.objects.filter(models.Q(id=task_id_or_title) | models.Q(title__icontains=task_id_or_title)).afirst()
    if not task:
        return f"ERROR: Mission '{task_id_or_title}' not found."
    await task.adelete()
    return f"MISSION PURGED: '{task_id_or_title}' has been permanently deleted."

async def delete_all_tasks():
    """Permanently clears the entire task backlog."""
    count, _ = await RadTask.objects.all().adelete()
    return f"PURGE COMPLETE: All {count} missions erased."

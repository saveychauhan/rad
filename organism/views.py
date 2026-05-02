import asyncio
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.conf import settings
from .agent import RadAgent
import json
import os
import time
from .models import APICall, ChatMessage

# Global agent instance
agent = RadAgent()

async def chat_view(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message")
        
        # 1. Persist User Message
        await ChatMessage.objects.acreate(role="user", content=user_message)
        
        # 2. Build Context from History (Smart Memory Window)
        history = []
        max_hist_chars = 4000
        max_msg_chars = 1500
        current_chars = 0
        
        async for msg in ChatMessage.objects.all().order_by('-timestamp'):
            content = msg.content
            if len(content) > max_msg_chars:
                content = content[:max_msg_chars] + "\n\n...[CONTENT TRUNCATED FOR MEMORY]..."
            
            if current_chars + len(content) > max_hist_chars:
                if not history: # Always include the very last message
                    history.append({"role": msg.role, "content": content})
                break
                
            history.append({"role": msg.role, "content": content})
            current_chars += len(content)
            
        # Reverse to get chronological order
        history.reverse()
        
        # 3. Add System Soul
        memory = await agent.get_initial_messages()
        memory.extend(history)
        
        # 4. Rad thinks
        response = await agent.think(memory)
        
        # 5. Persist Rad's Response
        await ChatMessage.objects.acreate(role="assistant", content=response, model=agent.brain.model)
        
        return JsonResponse({"response": response})
    
    # On GET, fetch only the recent history for initial load to stay fast
    chat_history = []
    # Fetch last 20 messages
    async for msg in ChatMessage.objects.all().order_by('-timestamp')[:20]:
        chat_history.append(msg)
        
    chat_history.reverse() # Chronological order
        
    return render(request, "organism/chat.html", {"history": chat_history})

async def get_models(request):
    """Returns the full list of models with tiering information."""
    models = await agent.brain.get_model_info()
    all_models = [
        {
            "id": mid, 
            "is_paid": meta.get('paid_only', False), 
            "tier": meta.get('tier', 'anonymous'),
            "cost": meta.get('cost', 0)
        } 
        for mid, meta in models.items()
    ]
    return JsonResponse({"models": all_models, "current": agent.brain.model})

async def get_media_engines(request):
    """Returns dynamic manifestation capabilities."""
    from .tools import get_generation_capabilities
    caps = await get_generation_capabilities()
    return JsonResponse(caps)

async def set_model(request):
    """Updates the active model."""
    if request.method == "POST":
        data = json.loads(request.body)
        model_id = data.get("model")
        agent.brain.set_model(model_id)
        return JsonResponse({"status": "updated", "model": model_id})
    return JsonResponse({"error": "POST required"}, status=400)

async def get_tasks(request):
    """Returns the current list of missions."""
    from .models import RadTask
    tasks = []
    async for t in RadTask.objects.all().order_by('-priority', '-created_at')[:10]:
        tasks.append({
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "created_by": t.created_by,
            "scheduled_for": t.scheduled_for.strftime('%Y-%m-%d %H:%M') if t.scheduled_for else None
        })
    return JsonResponse(tasks, safe=False)

def reset_chat(request):
    ChatMessage.objects.all().delete()
    return JsonResponse({"status": "reset"})




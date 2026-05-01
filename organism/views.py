import asyncio
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.conf import settings
from .agent import RadAgent
import json
import os
import time
from .models import APICall, SawanFact, ChatMessage

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
        max_hist_chars = 12000
        max_msg_chars = 3000
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
        await ChatMessage.objects.acreate(role="assistant", content=response)
        
        return JsonResponse({"response": response})
    
    # On GET, fetch only the recent history for initial load to stay fast
    chat_history = []
    # Fetch last 20 messages
    async for msg in ChatMessage.objects.all().order_by('-timestamp')[:20]:
        chat_history.append(msg)
        
    chat_history.reverse() # Chronological order
        
    return render(request, "organism/chat.html", {"history": chat_history})

async def get_models(request):
    """Returns the list of available free models."""
    models = await agent.brain.get_model_info()
    # Filter for free text models
    free_text_models = [
        {"id": mid, "cost": meta['cost']} 
        for mid, meta in models.items() 
        if not meta['paid_only']
    ]
    return JsonResponse({"models": free_text_models, "current": agent.brain.model})

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
            "priority": t.priority
        })
    return JsonResponse({"tasks": tasks})

def reset_chat(request):
    ChatMessage.objects.all().delete()
    return JsonResponse({"status": "reset"})




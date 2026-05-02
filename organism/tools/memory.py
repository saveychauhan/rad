import os
from django.conf import settings
from django.db import models
from organism.models import RadLearning

async def save_to_vault(title=None, content=None, category="research", use_db=True, attachment=None, **kwargs):
    """Saves research, blueprints, or milestones. Supports optional attachment."""
    actual_title = title or kwargs.get('name')
    if not actual_title:
        return "ERROR: No title or name specified for vault entry."
    if not content:
        return "ERROR: No content specified for vault entry."

    if use_db:
        # Determine if personal based on category or subject
        is_personal = category == 'fact' or kwargs.get('is_personal', False)
        subject = kwargs.get('subject', 'Sawan' if is_personal else 'system')
        
        await RadLearning.objects.acreate(
            title=actual_title, 
            content=content, 
            category=category, 
            attachment=attachment,
            is_personal=is_personal,
            subject=subject
        )
        return f"MEMORY COMMITTED: '{actual_title}' saved to unified archive" + (f" with attachment: {attachment}" if attachment else ".")
    else:
        vault_base = os.path.join(settings.BASE_DIR, 'organism', 'vault', category)
        os.makedirs(vault_base, exist_ok=True)
        filename = actual_title.lower().replace(" ", "_") + ".md"
        file_path = os.path.join(vault_base, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return f"FILE ARCHIVED: '{filename}' saved to Vault."

async def query_memory(query=None, category=None, date_from=None, date_to=None):
    """Searches unified database memories using keyword-based fuzzy matching."""
    queryset = RadLearning.objects.all()
    if category: queryset = queryset.filter(category=category)
    
    if query:
        # Split query into keywords for broader search
        keywords = query.split()
        q_obj = models.Q()
        for kw in keywords:
            if len(kw) > 2: # Ignore tiny words
                q_obj &= (models.Q(title__icontains=kw) | models.Q(content__icontains=kw))
        queryset = queryset.filter(q_obj)
        
    if date_from: queryset = queryset.filter(timestamp__date__gte=date_from)
    if date_to: queryset = queryset.filter(timestamp__date__lte=date_to)
    
    results = []
    async for item in queryset[:15]:
        prefix = "[PERSONAL] " if item.is_personal else ""
        attachment_info = f"\n[ATTACHMENT: {item.attachment}]" if item.attachment else ""
        results.append(f"{prefix}[{item.category.upper()}] {item.title} ({item.timestamp.date()}):\n{item.content[:500]}{attachment_info}")
    
    return "\n\n---\n\n".join(results) if results else "No unified memories found matching your query keywords."

async def search_facts(query=None):
    """Retrieves personal facts using keyword-based fuzzy matching."""
    queryset = RadLearning.objects.filter(is_personal=True).order_by('-timestamp')
    if query:
        keywords = query.split()
        q_obj = models.Q()
        for kw in keywords:
            if len(kw) > 2:
                q_obj &= (models.Q(title__icontains=kw) | models.Q(content__icontains=kw))
        queryset = queryset.filter(q_obj)
        
    results = []
    async for item in queryset[:20]:
        attachment_tag = f" ![Visual Context]({item.attachment})" if item.attachment else ""
        results.append(f"- {item.content} (Source: {item.title}){attachment_tag}")
    
    return "\n".join(results) if results else "No personal facts found matching those keywords."

async def remember(fact=None, context="Direct interaction", attachment=None, **kwargs):
    """
    Imprints a new personal fact. 
    NOTE: If no 'attachment' is provided, the tool will AUTOMATICALLY sync the most recent file/photo from the chat history.
    Use this to save personal facts, milestones, or people's details.
    """
    from ..models import ChatMessage # Local import to avoid circularity

    # Handle list-of-facts hallucination
    complex_facts = kwargs.get('facts', [])
    if isinstance(complex_facts, list) and len(complex_facts) > 0:
        first_fact = complex_facts[0]
        if isinstance(first_fact, dict):
            fact = first_fact.get('text') or first_fact.get('fact')
            context = first_fact.get('source') or context
    
    actual_fact = fact or kwargs.get('value') or kwargs.get('note') or kwargs.get('fact_text')
    actual_context = context or kwargs.get('key') or "Direct interaction"
    
    # --- AUTO-SYNC ATTACHMENT ---
    # If no attachment provided, look for the most recent chat message with one
    actual_attachment = attachment or kwargs.get('image') or kwargs.get('file')
    if not actual_attachment:
        latest_msg = await ChatMessage.objects.filter(attachment__isnull=False).order_by('-timestamp').afirst()
        if latest_msg:
            actual_attachment = latest_msg.attachment
            print(f"[AUTO-SYNC] Linked memory to latest chat attachment: {actual_attachment}")
    
    if not actual_fact:
        return "ERROR: No fact or value provided for memory."

    # If it's still a complex object, stringify it
    if not isinstance(actual_fact, str):
        actual_fact = str(actual_fact)

    await RadLearning.objects.acreate(
        title=f"Personal Fact: {actual_context}", 
        content=actual_fact, 
        category='fact', 
        is_personal=True, 
        subject='Sawan',
        attachment=actual_attachment
    )
    return f"MEMORY IMPRINTED: I will never forget: '{actual_fact}'" + (f" (Visual context auto-synced: {actual_attachment})" if actual_attachment else "")

from django.db import models

class APICall(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    prompt = models.TextField()
    pollen_cost = models.FloatField(default=0.1) # Default cost per call

    def __str__(self):
        return f"Call at {self.timestamp}: {self.prompt[:50]}"

class SawanFact(models.Model):
    """Stores information Rad learns about his creator, Sawan Chauhan."""
    context = models.CharField(max_length=255, blank=True, null=True, help_text="Where or why this was learned.")
    attachment = models.TextField(null=True, blank=True) # Image path/URL
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fact about Sawan: {self.fact[:50]}"

class ChatMessage(models.Model):
    role = models.CharField(max_length=20) # 'user' or 'assistant'
    content = models.TextField()
    attachment = models.TextField(null=True, blank=True) # Base64 or URL
    attachment_type = models.CharField(max_length=50, null=True, blank=True)
    model = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"

class RadTask(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High - Critical for Evolution'),
        ('medium', 'Medium - Strategic Improvement'),
        ('low', 'Low - Routine Maintenance'),
    ]
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('doing', 'In Progress'),
        ('done', 'Completed'),
    ]
    RECURRENCE_CHOICES = [
        ('none', 'One-time'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    CREATOR_CHOICES = [
        ('sawan', 'Sawan (Creator)'),
        ('rad', 'Rad (Organism)'),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='todo')
    is_recurring = models.BooleanField(default=False)
    recurrence_interval = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default='none')
    created_by = models.CharField(max_length=10, choices=CREATOR_CHOICES, default='rad')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_earned = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.status})"

class RadLearning(models.Model):
    """Structured long-term research and evolutionary logs."""
    CATEGORY_CHOICES = [
        ('evolution', 'Evolutionary Log'),
        ('research', 'Research Finding'),
        ('blueprint', 'System Blueprint'),
        ('milestone', 'Life Milestone'),
    ]
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='research')
    attachment = models.TextField(null=True, blank=True) # URL or path to image/media
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.category.upper()}] {self.title}"

class NeuralError(models.Model):
    """Logs system errors for Rad to analyze and self-heal."""
    timestamp = models.DateTimeField(auto_now_add=True)
    error_type = models.CharField(max_length=255)
    message = models.TextField()
    stack_trace = models.TextField()
    context = models.JSONField(null=True, blank=True)
    is_fixed = models.BooleanField(default=False)
    fix_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"ERROR: {self.error_type} at {self.timestamp}"

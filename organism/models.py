from django.db import models

class APICall(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    prompt = models.TextField()
    pollen_cost = models.FloatField(default=0.1) # Default cost per call

    def __str__(self):
        return f"Call at {self.timestamp}: {self.prompt[:50]}"

class SawanFact(models.Model):
    """Stores information Rad learns about his creator, Sawan Chauhan."""
    timestamp = models.DateTimeField(auto_now_add=True)
    fact = models.TextField(help_text="A specific fact or preference about Sawan.")
    context = models.CharField(max_length=255, blank=True, null=True, help_text="Where or why this was learned.")

    def __str__(self):
        return f"Fact about Sawan: {self.fact[:50]}"

class ChatMessage(models.Model):
    role = models.CharField(max_length=20) # 'user' or 'assistant'
    content = models.TextField()
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
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='todo')
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
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.category.upper()}] {self.title}"

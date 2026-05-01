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

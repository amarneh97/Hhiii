"""حسابات معدل التفاعل (Engagement Rate) المشتركة بين مصدري البيانات."""
from dataclasses import dataclass, field
from statistics import mean


@dataclass
class PostStats:
    post_id: str
    likes: int
    comments: int
    timestamp: str = ""
    permalink: str = ""
    caption: str = ""

    @property
    def interactions(self) -> int:
        return self.likes + self.comments


@dataclass
class EngagementReport:
    account: str
    followers: int
    posts: list = field(default_factory=list)

    @property
    def avg_likes(self) -> float:
        return mean(p.likes for p in self.posts) if self.posts else 0.0

    @property
    def avg_comments(self) -> float:
        return mean(p.comments for p in self.posts) if self.posts else 0.0

    @property
    def avg_interactions(self) -> float:
        return mean(p.interactions for p in self.posts) if self.posts else 0.0

    @property
    def engagement_rate(self) -> float:
        """نسبة التفاعل = متوسط (لايكات + تعليقات) لكل منشور ÷ عدد المتابعين × 100."""
        if not self.followers or not self.posts:
            return 0.0
        return (self.avg_interactions / self.followers) * 100

    def top_posts(self, n: int = 5) -> list:
        return sorted(self.posts, key=lambda p: p.interactions, reverse=True)[:n]

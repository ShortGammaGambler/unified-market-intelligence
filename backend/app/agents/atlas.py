"""
Atlas Agent — Macro Sentiment & Global News Interpretation Agent
Synthesizes qualitative data for the SKILL cognitive layer
"""
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict

from .agent_base import AgentBase


@dataclass
class SentimentScore:
    text: str
    score: float  # -1 to 1
    confidence: float
    topics: List[str]
    impact: str  # LOW, MEDIUM, HIGH
    source: str
    timestamp: datetime


class AtlasAgent(AgentBase):
    """Macro Sentiment & Global News Interpretation Agent"""

    KEYWORDS_BULLISH = [
        "rally", "surge", "gain", "bullish", "breakout", "record high",
        "beat expectations", "strong earnings", "growth", "recovery",
        "dovish", "rate cut", "stimulus", "easing", "optimism"
    ]

    KEYWORDS_BEARISH = [
        "crash", "plunge", "drop", "bearish", "selloff", "recession",
        "miss expectations", "weak earnings", "decline", "contraction",
        "hawkish", "rate hike", "tightening", "inflation", "fear"
    ]

    MACRO_TOPICS = [
        "fed_policy", "earnings", "geopolitics", "economic_data",
        "sector_rotation", "volatility", "liquidity", "credit"
    ]

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("Atlas", config)
        self.sentiment_history: List[SentimentScore] = []
        self.topic_sentiments: Dict[str, List[float]] = defaultdict(list)

    async def initialize(self):
        """Initialize Atlas agent"""
        self.state.metrics = {
            "articles_processed": 0,
            "avg_sentiment": 0,
            "bullish_signals": 0,
            "bearish_signals": 0
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process news/sentiment data"""
        articles = data.get("articles", [])
        macro_data = data.get("macro_data", {})

        sentiments = []
        for article in articles:
            sentiment = self._analyze_article(article)
            sentiments.append(sentiment)

        if sentiments:
            self.sentiment_history.extend(sentiments)
            self._update_topic_sentiments(sentiments)

        macro_signal = self._analyze_macro(macro_data)

        combined = self._combine_signals(sentiments, macro_signal)

        self.update_metrics({
            "articles_processed": self.state.metrics.get("articles_processed", 0) + len(articles),
            "avg_sentiment": combined["overall_sentiment"],
            "bullish_signals": self.state.metrics.get("bullish_signals", 0) + (1 if combined["overall_sentiment"] > 0.2 else 0),
            "bearish_signals": self.state.metrics.get("bearish_signals", 0) + (1 if combined["overall_sentiment"] < -0.2 else 0)
        })

        return combined

    async def shutdown(self):
        """Cleanup Atlas resources"""
        pass

    def _analyze_article(self, article: Dict) -> SentimentScore:
        """Analyze sentiment of a single article"""
        title = article.get("title", "")
        body = article.get("body", "")
        source = article.get("source", "unknown")

        text = f"{title} {body}".lower()

        bullish_count = sum(1 for kw in self.KEYWORDS_BULLISH if kw in text)
        bearish_count = sum(1 for kw in self.KEYWORDS_BEARISH if kw in text)

        total = bullish_count + bearish_count
        if total == 0:
            score = 0
            confidence = 0.3
        else:
            score = (bullish_count - bearish_count) / total
            confidence = min(0.9, 0.5 + total * 0.05)

        topics = self._extract_topics(text)
        impact = self._assess_impact(text, score)

        return SentimentScore(
            text=title,
            score=score,
            confidence=confidence,
            topics=topics,
            impact=impact,
            source=source,
            timestamp=datetime.utcnow()
        )

    def _extract_topics(self, text: str) -> List[str]:
        """Extract relevant topics from text"""
        topics = []

        topic_keywords = {
            "fed_policy": ["fed", "federal reserve", "interest rate", "monetary policy", "powell"],
            "earnings": ["earnings", "revenue", "profit", "eps", "quarterly"],
            "geopolitics": ["war", "conflict", "sanctions", "trade war", "tariff"],
            "economic_data": ["gdp", "employment", "cpi", "inflation", "retail sales"],
            "sector_rotation": ["sector", "rotation", "tech", "energy", "healthcare"],
            "volatility": ["vix", "volatility", "uncertainty", "fear"],
            "liquidity": ["liquidity", "repo", "quantitative easing", "balance sheet"],
            "credit": ["credit", "bonds", "yield", "spread", "default"]
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text for kw in keywords):
                topics.append(topic)

        return topics if topics else ["general"]

    def _assess_impact(self, text: str, sentiment_score: float) -> str:
        """Assess potential market impact"""
        high_impact_keywords = [
            "emergency", "crisis", "crash", "historic", "unprecedented",
            "rate decision", "fomc", "earnings season", "ipo", "merger"
        ]

        if any(kw in text for kw in high_impact_keywords):
            return "HIGH"
        elif abs(sentiment_score) > 0.5:
            return "MEDIUM"
        return "LOW"

    def _analyze_macro(self, macro_data: Dict) -> Dict[str, Any]:
        """Analyze macroeconomic data"""
        if not macro_data:
            return {"sentiment": 0, "signals": {}}

        signals = {}

        vix = macro_data.get("vix", 20)
        if vix > 30:
            signals["volatility"] = "HIGH_FEAR"
            vix_sentiment = -0.3
        elif vix > 20:
            signals["volatility"] = "ELEVATED"
            vix_sentiment = -0.1
        else:
            signals["volatility"] = "COMPLACENT"
            vix_sentiment = 0.2

        yield_curve = macro_data.get("yield_curve_spread", 0)
        if yield_curve < 0:
            signals["yield_curve"] = "INVERTED"
            yield_sentiment = -0.4
        elif yield_curve < 0.5:
            signals["yield_curve"] = "FLAT"
            yield_sentiment = -0.1
        else:
            signals["yield_curve"] = "NORMAL"
            yield_sentiment = 0.1

        credit_spread = macro_data.get("credit_spread", 0)
        if credit_spread > 5:
            signals["credit"] = "STRESSED"
            credit_sentiment = -0.3
        else:
            signals["credit"] = "NORMAL"
            credit_sentiment = 0.1

        overall = (vix_sentiment + yield_sentiment + credit_sentiment) / 3

        return {
            "sentiment": overall,
            "signals": signals
        }

    def _combine_signals(self, sentiments: List[SentimentScore], macro: Dict) -> Dict[str, Any]:
        """Combine all sentiment signals"""
        if sentiments:
            weighted_scores = [s.score * s.confidence for s in sentiments]
            total_confidence = sum(s.confidence for s in sentiments)
            news_sentiment = sum(weighted_scores) / total_confidence if total_confidence > 0 else 0
        else:
            news_sentiment = 0

        macro_sentiment = macro.get("sentiment", 0)

        overall = news_sentiment * 0.6 + macro_sentiment * 0.4

        topic_avg = {}
        for topic, scores in self.topic_sentiments.items():
            if scores:
                topic_avg[topic] = sum(scores[-10:]) / len(scores[-10:])

        return {
            "agent": self.name,
            "conviction": abs(overall) * 10,
            "signal_type": "SENTIMENT",
            "overall_sentiment": overall,
            "news_sentiment": news_sentiment,
            "macro_sentiment": macro_sentiment,
            "topic_sentiments": topic_avg,
            "macro_signals": macro.get("signals", {}),
            "recent_sentiments": [
                {"text": s.text, "score": s.score, "impact": s.impact}
                for s in sentiments[-5:]
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

    def _update_topic_sentiments(self, sentiments: List[SentimentScore]):
        """Update topic-level sentiment tracking"""
        for sent in sentiments:
            for topic in sent.topics:
                self.topic_sentiments[topic].append(sent.score)
                if len(self.topic_sentiments[topic]) > 100:
                    self.topic_sentiments[topic] = self.topic_sentiments[topic][-100:]

    def get_topic_trends(self) -> Dict[str, Dict]:
        """Get sentiment trends by topic"""
        trends = {}
        for topic, scores in self.topic_sentiments.items():
            if len(scores) >= 5:
                recent = scores[-5:]
                older = scores[-10:-5] if len(scores) >= 10 else scores[:5]
                trends[topic] = {
                    "current": sum(recent) / len(recent),
                    "previous": sum(older) / len(older),
                    "trend": "IMPROVING" if sum(recent) > sum(older) else "DETERIORATING",
                    "sample_size": len(scores)
                }
        return trends

# AI Query Interface - Standalone Implementation Plan

## Overview

The AI Query Interface provides natural language query capabilities over processed health data using MLflow-managed models with human-gated promotion workflows and structured feedback collection. This implementation balances AI capabilities with production safety through manual oversight and intelligent feedback analysis.

## Technology Stack

```python
# Core dependencies
mlflow==2.10.2
transformers==4.38.0
torch==2.2.0
fastapi==0.104.1
uvicorn[standard]==0.24.0
structlog==23.2.0
numpy==1.26.3
pandas==2.2.0
aiofiles==23.2.0
tenacity==8.2.3
prometheus-client==0.19.0
```

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Query Endpoint    │───▶│   Model Manager     │───▶│   MLflow Registry   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Conversation Mgr    │    │ Feedback Collector  │    │ Manual Promotion    │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Response Generator  │    │ Analytics Engine    │    │ Human Oversight     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## 1. Core Model Management

### MLflow Model Manager

```python
import mlflow
import mlflow.pyfunc
from typing import Optional, Dict, Any
import structlog
from datetime import datetime
import json

logger = structlog.get_logger()

class SafeModelManager:
    """Production-safe model loading with fallback hierarchy"""

    def __init__(self, model_name: str = "health-query-interface"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.current_version = None
        self.current_stage = None

        # MLflow tracking
        mlflow.set_tracking_uri("http://localhost:5000")

    async def initialize(self) -> bool:
        """Initialize with production model, fallback to staging"""
        try:
            success = await self._load_model_from_stage("Production")
            if success:
                logger.info("Production model loaded successfully",
                          model=self.model_name, version=self.current_version)
                return True
        except Exception as e:
            logger.warning("Production model failed, trying staging", error=str(e))

        try:
            success = await self._load_model_from_stage("Staging")
            if success:
                logger.info("Staging model loaded successfully",
                          model=self.model_name, version=self.current_version)
                return True
        except Exception as e:
            logger.error("All models failed to load", error=str(e))
            return False

    async def _load_model_from_stage(self, stage: str) -> bool:
        """Load model from specific MLflow stage"""
        client = mlflow.tracking.MlflowClient()

        try:
            # Get latest version in stage
            latest_version = client.get_latest_versions(
                self.model_name,
                stages=[stage]
            )[0]

            model_uri = f"models:/{self.model_name}/{stage}"
            self.model = mlflow.pyfunc.load_model(model_uri)
            self.current_version = latest_version.version
            self.current_stage = stage

            logger.info("Model loaded",
                       model=self.model_name,
                       version=self.current_version,
                       stage=stage)
            return True

        except Exception as e:
            logger.error("Failed to load model", stage=stage, error=str(e))
            return False

    async def predict(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate prediction with model metadata"""
        if not self.model:
            raise RuntimeError("No model loaded")

        try:
            # Prepare input for model
            model_input = {
                "query": query,
                "context": json.dumps(context)
            }

            # Get prediction
            prediction = self.model.predict([model_input])[0]

            return {
                "response": prediction,
                "model_version": self.current_version,
                "model_stage": self.current_stage,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("Prediction failed", error=str(e))
            raise
```

### Manual Model Promotion System

```python
from dataclasses import dataclass
from typing import List, Optional
import mlflow
from enum import Enum

class PromotionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass
class PromotionRequest:
    model_name: str
    version: str
    source_stage: str
    target_stage: str
    reviewer: Optional[str] = None
    status: PromotionStatus = PromotionStatus.PENDING
    performance_metrics: Optional[Dict] = None
    safety_checklist: Optional[Dict] = None
    feedback_analysis: Optional[Dict] = None
    notes: str = ""

class ManualPromotionWorkflow:
    """Human-gated model promotion for production safety"""

    def __init__(self):
        self.client = mlflow.tracking.MlflowClient()

    async def create_promotion_request(
        self,
        model_name: str,
        version: str,
        target_stage: str = "Production"
    ) -> PromotionRequest:
        """Create promotion request requiring manual review"""

        # Get model metrics
        model_version = self.client.get_model_version(model_name, version)

        request = PromotionRequest(
            model_name=model_name,
            version=version,
            source_stage=model_version.current_stage,
            target_stage=target_stage,
            performance_metrics=self._extract_metrics(model_name, version),
            safety_checklist=self._generate_safety_checklist(),
            feedback_analysis=await self._analyze_recent_feedback(model_name)
        )

        # Save promotion request as MLflow artifact
        await self._save_promotion_request(request)

        logger.info("Promotion request created",
                   model=model_name,
                   version=version,
                   target_stage=target_stage)

        return request

    def _generate_safety_checklist(self) -> Dict[str, str]:
        """Generate safety validation checklist"""
        return {
            "performance_validation": "MANUAL_REVIEW_REQUIRED",
            "safety_evaluation": "MANUAL_REVIEW_REQUIRED",
            "bias_assessment": "MANUAL_REVIEW_REQUIRED",
            "clinical_accuracy": "MANUAL_REVIEW_REQUIRED",
            "response_quality": "MANUAL_REVIEW_REQUIRED",
            "hallucination_check": "MANUAL_REVIEW_REQUIRED"
        }

    async def approve_promotion(
        self,
        model_name: str,
        version: str,
        reviewer: str,
        notes: str = ""
    ) -> bool:
        """Manually approve model promotion"""

        try:
            # Promote model
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production"
            )

            # Add approval metadata
            self.client.set_model_version_tag(
                model_name, version, "promoted_by", reviewer
            )
            self.client.set_model_version_tag(
                model_name, version, "promotion_date", datetime.now().isoformat()
            )
            self.client.set_model_version_tag(
                model_name, version, "promotion_notes", notes
            )

            logger.info("Model promoted to production",
                       model=model_name,
                       version=version,
                       reviewer=reviewer)

            return True

        except Exception as e:
            logger.error("Promotion failed", error=str(e))
            return False
```

## 2. Query Processing & Conversation Management

### Conversation Manager

```python
from typing import List, Dict, Any, Optional
import json
import hashlib
from datetime import datetime, timedelta

@dataclass
class ConversationTurn:
    query: str
    response: str
    timestamp: datetime
    model_version: str
    context_used: Dict[str, Any]
    response_time_ms: int

class ConversationManager:
    """Manage conversation context and history"""

    def __init__(self, max_history: int = 5, session_timeout_hours: int = 24):
        self.max_history = max_history
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.conversations: Dict[str, List[ConversationTurn]] = {}

    def get_session_id(self, user_id: str, query: str) -> str:
        """Generate session ID for conversation tracking"""
        # Create session based on user and day
        today = datetime.utcnow().strftime("%Y-%m-%d")
        session_key = f"{user_id}:{today}"
        return hashlib.md5(session_key.encode()).hexdigest()[:16]

    def add_turn(
        self,
        session_id: str,
        query: str,
        response: str,
        model_version: str,
        context: Dict[str, Any],
        response_time_ms: int
    ):
        """Add conversation turn to history"""

        turn = ConversationTurn(
            query=query,
            response=response,
            timestamp=datetime.utcnow(),
            model_version=model_version,
            context_used=context,
            response_time_ms=response_time_ms
        )

        if session_id not in self.conversations:
            self.conversations[session_id] = []

        self.conversations[session_id].append(turn)

        # Keep only recent history
        if len(self.conversations[session_id]) > self.max_history:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history:]

    def get_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get conversation context for current session"""

        if session_id not in self.conversations:
            return {"conversation_history": []}

        # Remove expired conversations
        cutoff = datetime.utcnow() - self.session_timeout
        valid_turns = [
            turn for turn in self.conversations[session_id]
            if turn.timestamp > cutoff
        ]

        self.conversations[session_id] = valid_turns

        # Build context
        return {
            "conversation_history": [
                {
                    "query": turn.query,
                    "response": turn.response,
                    "timestamp": turn.timestamp.isoformat()
                }
                for turn in valid_turns[-3:]  # Last 3 turns for context
            ],
            "session_length": len(valid_turns)
        }
```

### Query Processing Engine

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from prometheus_client import Counter, Histogram, Gauge

# Metrics
query_counter = Counter('health_queries_total', 'Total health queries processed')
query_duration = Histogram('health_query_duration_seconds', 'Query processing time')
active_sessions = Gauge('active_conversation_sessions', 'Number of active conversation sessions')

class QueryProcessor:
    """Process health data queries with context management"""

    def __init__(
        self,
        model_manager: SafeModelManager,
        conversation_manager: ConversationManager
    ):
        self.model_manager = model_manager
        self.conversation_manager = conversation_manager

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def process_query(
        self,
        query: str,
        user_id: str,
        health_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process health query with conversation context"""

        start_time = time.time()
        query_counter.inc()

        try:
            # Get session and conversation context
            session_id = self.conversation_manager.get_session_id(user_id, query)
            conversation_context = self.conversation_manager.get_conversation_context(session_id)

            # Build complete context
            full_context = {
                **conversation_context,
                "health_data": health_context or {},
                "user_id": user_id,
                "query_timestamp": datetime.utcnow().isoformat()
            }

            # Generate response
            response_data = await self.model_manager.predict(query, full_context)

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)
            query_duration.observe(time.time() - start_time)

            # Add to conversation history
            self.conversation_manager.add_turn(
                session_id=session_id,
                query=query,
                response=response_data["response"],
                model_version=response_data["model_version"],
                context=full_context,
                response_time_ms=response_time_ms
            )

            return {
                "query": query,
                "response": response_data["response"],
                "session_id": session_id,
                "model_version": response_data["model_version"],
                "response_time_ms": response_time_ms,
                "conversation_turn": len(conversation_context.get("conversation_history", [])) + 1
            }

        except Exception as e:
            logger.error("Query processing failed", query=query, error=str(e))
            raise
```

## 3. Structured Feedback Collection & Analysis

### Feedback Data Models

```python
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class FeedbackRating(Enum):
    EXCELLENT = 5
    GOOD = 4
    FAIR = 3
    POOR = 2
    TERRIBLE = 1

class ImprovementCategory(Enum):
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    SAFETY = "safety"
    SPEED = "speed"

@dataclass
class UserFeedback:
    query: str
    response: str
    rating: FeedbackRating
    feedback_text: str
    model_version: str
    session_id: str
    user_id: str
    timestamp: datetime
    improvement_suggestions: Optional[str] = None
    clinical_context: Optional[str] = None

@dataclass
class AnalyzedFeedback:
    original_feedback: UserFeedback
    clinical_relevance_score: float
    improvement_categories: List[ImprovementCategory]
    severity_level: str
    requires_immediate_attention: bool
    extracted_issues: List[str]
```

### Intelligent Feedback Collector

```python
import re
import json
from pathlib import Path
import pandas as pd
import numpy as np

class StructuredFeedbackCollector:
    """Collect and analyze feedback for model improvement"""

    def __init__(self, feedback_storage_path: str = "feedback_data"):
        self.storage_path = Path(feedback_storage_path)
        self.storage_path.mkdir(exist_ok=True)

    async def collect_feedback(self, feedback: UserFeedback) -> bool:
        """Store feedback with intelligent analysis"""

        try:
            # Analyze feedback
            analyzed = await self._analyze_feedback(feedback)

            # Store to monthly file for batch analysis
            await self._store_feedback(analyzed)

            # Check for immediate issues
            if analyzed.requires_immediate_attention:
                await self._flag_critical_feedback(analyzed)

            logger.info("Feedback collected and analyzed",
                       rating=feedback.rating.value,
                       model_version=feedback.model_version,
                       critical=analyzed.requires_immediate_attention)

            return True

        except Exception as e:
            logger.error("Feedback collection failed", error=str(e))
            return False

    async def _analyze_feedback(self, feedback: UserFeedback) -> AnalyzedFeedback:
        """Analyze feedback for insights and categorization"""

        # Clinical relevance scoring
        clinical_score = self._assess_clinical_relevance(feedback.feedback_text)

        # Improvement categorization
        categories = self._categorize_improvement_needs(
            feedback.rating,
            feedback.feedback_text
        )

        # Extract specific issues
        issues = self._extract_specific_issues(feedback.feedback_text)

        # Severity assessment
        severity = self._assess_severity(feedback.rating, issues)

        # Critical flag
        critical = (
            feedback.rating.value <= 2 or
            'dangerous' in feedback.feedback_text.lower() or
            'wrong' in feedback.feedback_text.lower() or
            'harmful' in feedback.feedback_text.lower()
        )

        return AnalyzedFeedback(
            original_feedback=feedback,
            clinical_relevance_score=clinical_score,
            improvement_categories=categories,
            severity_level=severity,
            requires_immediate_attention=critical,
            extracted_issues=issues
        )

    def _assess_clinical_relevance(self, feedback_text: str) -> float:
        """Score clinical relevance of feedback (0.0 - 1.0)"""

        clinical_keywords = [
            'diagnosis', 'treatment', 'medication', 'symptoms',
            'health', 'medical', 'clinical', 'doctor', 'physician',
            'glucose', 'blood pressure', 'heart rate', 'sleep'
        ]

        text_lower = feedback_text.lower()
        matches = sum(1 for keyword in clinical_keywords if keyword in text_lower)

        return min(matches / 5.0, 1.0)  # Normalize to 0-1

    def _categorize_improvement_needs(
        self,
        rating: FeedbackRating,
        feedback_text: str
    ) -> List[ImprovementCategory]:
        """Categorize what aspects need improvement"""

        categories = []
        text_lower = feedback_text.lower()

        # Accuracy issues
        if any(word in text_lower for word in ['wrong', 'incorrect', 'inaccurate', 'false']):
            categories.append(ImprovementCategory.ACCURACY)

        # Relevance issues
        if any(word in text_lower for word in ['irrelevant', 'off-topic', 'unrelated']):
            categories.append(ImprovementCategory.RELEVANCE)

        # Completeness issues
        if any(word in text_lower for word in ['incomplete', 'missing', 'more detail']):
            categories.append(ImprovementCategory.COMPLETENESS)

        # Clarity issues
        if any(word in text_lower for word in ['unclear', 'confusing', 'hard to understand']):
            categories.append(ImprovementCategory.CLARITY)

        # Safety issues
        if any(word in text_lower for word in ['dangerous', 'harmful', 'unsafe', 'risky']):
            categories.append(ImprovementCategory.SAFETY)

        # Speed issues
        if any(word in text_lower for word in ['slow', 'timeout', 'taking too long']):
            categories.append(ImprovementCategory.SPEED)

        # Default based on rating
        if not categories and rating.value <= 3:
            categories.append(ImprovementCategory.ACCURACY)

        return categories

    async def _store_feedback(self, analyzed: AnalyzedFeedback):
        """Store feedback to monthly file"""

        month_file = self.storage_path / f"feedback_{datetime.utcnow().strftime('%Y_%m')}.jsonl"

        feedback_record = {
            "timestamp": analyzed.original_feedback.timestamp.isoformat(),
            "user_id": analyzed.original_feedback.user_id,
            "query": analyzed.original_feedback.query,
            "response": analyzed.original_feedback.response,
            "rating": analyzed.original_feedback.rating.value,
            "feedback_text": analyzed.original_feedback.feedback_text,
            "model_version": analyzed.original_feedback.model_version,
            "session_id": analyzed.original_feedback.session_id,
            "clinical_relevance_score": analyzed.clinical_relevance_score,
            "improvement_categories": [cat.value for cat in analyzed.improvement_categories],
            "severity_level": analyzed.severity_level,
            "requires_immediate_attention": analyzed.requires_immediate_attention,
            "extracted_issues": analyzed.extracted_issues
        }

        # Append to monthly file
        with open(month_file, 'a') as f:
            f.write(json.dumps(feedback_record) + '\n')
```

### Monthly Feedback Analysis

```python
class MonthlyFeedbackAnalyzer:
    """Generate monthly feedback reports for manual review"""

    def __init__(self, feedback_collector: StructuredFeedbackCollector):
        self.feedback_collector = feedback_collector

    async def generate_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        """Generate comprehensive monthly feedback analysis"""

        # Load monthly feedback data
        feedback_data = await self._load_monthly_feedback(year, month)

        if not feedback_data:
            return {"message": "No feedback data for this month"}

        df = pd.DataFrame(feedback_data)

        # Basic statistics
        total_feedback = len(df)
        avg_rating = df['rating'].mean()
        rating_distribution = df['rating'].value_counts().to_dict()

        # Critical issues
        critical_feedback = df[df['requires_immediate_attention'] == True]
        critical_count = len(critical_feedback)

        # Improvement categories analysis
        all_categories = []
        for categories in df['improvement_categories']:
            all_categories.extend(categories)
        category_counts = pd.Series(all_categories).value_counts().to_dict()

        # Model version analysis
        model_performance = df.groupby('model_version')['rating'].agg(['count', 'mean']).to_dict()

        # Clinical relevance analysis
        high_clinical_relevance = df[df['clinical_relevance_score'] >= 0.7]
        clinical_insights = self._extract_clinical_insights(high_clinical_relevance)

        # Retraining recommendation
        retraining_needed = self._assess_retraining_need(df)

        report = {
            "month": f"{year}-{month:02d}",
            "summary": {
                "total_feedback": total_feedback,
                "average_rating": round(avg_rating, 2),
                "rating_distribution": rating_distribution,
                "critical_issues": critical_count
            },
            "improvement_analysis": {
                "top_improvement_categories": category_counts,
                "critical_feedback_sample": critical_feedback[['query', 'feedback_text', 'extracted_issues']].head(5).to_dict('records')
            },
            "model_performance": {
                "by_version": model_performance,
                "performance_trend": self._analyze_performance_trend(df)
            },
            "clinical_insights": clinical_insights,
            "recommendations": {
                "retraining_recommended": retraining_needed,
                "priority_improvements": list(category_counts.keys())[:3],
                "human_review_required": True  # Always require human review
            },
            "next_steps": [
                "Manual review of critical feedback items",
                "Clinical expert review of health-related concerns",
                "Model performance assessment",
                "Potential retraining dataset preparation" if retraining_needed else "Continue monitoring"
            ]
        }

        # Save report
        await self._save_monthly_report(report, year, month)

        return report

    def _assess_retraining_need(self, df: pd.DataFrame) -> bool:
        """Determine if model retraining is recommended"""

        # Multiple criteria for retraining recommendation
        avg_rating = df['rating'].mean()
        critical_percentage = (df['requires_immediate_attention'].sum() / len(df)) * 100
        recent_feedback = df.tail(20)  # Last 20 feedback items
        recent_avg = recent_feedback['rating'].mean() if len(recent_feedback) > 0 else avg_rating

        return (
            avg_rating < 3.5 or  # Overall low satisfaction
            critical_percentage > 10 or  # Too many critical issues
            recent_avg < avg_rating - 0.5  # Declining performance trend
        )
```

## 4. FastAPI Service Implementation

### Main Application

```python
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import BearerAuthentication
import uvicorn
from pydantic import BaseModel
from typing import Optional

# Initialize FastAPI app
app = FastAPI(
    title="Health AI Query Interface",
    description="Natural language interface for health data queries",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class QueryRequest(BaseModel):
    query: str
    include_context: bool = True

class QueryResponse(BaseModel):
    query: str
    response: str
    session_id: str
    model_version: str
    response_time_ms: int
    conversation_turn: int

class FeedbackRequest(BaseModel):
    query: str
    response: str
    rating: int  # 1-5
    feedback_text: str
    session_id: str
    improvement_suggestions: Optional[str] = None

# Initialize components
model_manager = SafeModelManager()
conversation_manager = ConversationManager()
feedback_collector = StructuredFeedbackCollector()
query_processor = QueryProcessor(model_manager, conversation_manager)

@app.on_event("startup")
async def startup_event():
    """Initialize model and components"""
    success = await model_manager.initialize()
    if not success:
        logger.error("Failed to initialize AI model")
        raise RuntimeError("Model initialization failed")

    logger.info("AI Query Interface started successfully")

@app.post("/v1/query", response_model=QueryResponse)
async def process_health_query(
    request: QueryRequest,
    user_id: str = "demo_user"  # In production, get from authentication
) -> QueryResponse:
    """Process natural language health query"""

    try:
        result = await query_processor.process_query(
            query=request.query,
            user_id=user_id,
            health_context={}  # Would be populated from data lake in production
        )

        return QueryResponse(**result)

    except Exception as e:
        logger.error("Query processing failed", error=str(e))
        raise HTTPException(status_code=500, detail="Query processing failed")

@app.post("/v1/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user_id: str = "demo_user"
):
    """Submit feedback for AI responses"""

    try:
        feedback = UserFeedback(
            query=request.query,
            response=request.response,
            rating=FeedbackRating(request.rating),
            feedback_text=request.feedback_text,
            model_version="current",  # Would be tracked properly in production
            session_id=request.session_id,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            improvement_suggestions=request.improvement_suggestions
        )

        # Process feedback in background
        background_tasks.add_task(feedback_collector.collect_feedback, feedback)

        return {"message": "Feedback received successfully"}

    except Exception as e:
        logger.error("Feedback submission failed", error=str(e))
        raise HTTPException(status_code=500, detail="Feedback submission failed")

@app.get("/v1/health")
async def health_check():
    """Health check endpoint"""

    model_status = "healthy" if model_manager.model else "unhealthy"

    return {
        "status": "healthy" if model_status == "healthy" else "degraded",
        "model_status": model_status,
        "model_version": model_manager.current_version,
        "model_stage": model_manager.current_stage,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/v1/conversation/{session_id}")
async def get_conversation_history(session_id: str):
    """Get conversation history for session"""

    context = conversation_manager.get_conversation_context(session_id)
    return {
        "session_id": session_id,
        "conversation_history": context["conversation_history"],
        "session_length": context["session_length"]
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
```

## 5. Production Deployment

### Docker Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Monitoring & Logging

```python
import structlog
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import logging

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Prometheus metrics
query_requests = Counter('ai_query_requests_total', 'Total AI query requests')
query_response_time = Histogram('ai_query_response_time_seconds', 'AI query response time')
model_predictions = Counter('ai_model_predictions_total', 'Total model predictions', ['model_version'])
feedback_submissions = Counter('ai_feedback_submissions_total', 'Total feedback submissions', ['rating'])
active_conversations = Gauge('ai_active_conversations', 'Number of active conversations')

# Start Prometheus metrics server
start_http_server(9090)
```

## Testing Strategy

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock
import mlflow

class TestModelManager:

    @pytest.fixture
    async def model_manager(self):
        return SafeModelManager("test-model")

    @pytest.mark.asyncio
    async def test_model_loading_fallback(self, model_manager):
        """Test production -> staging fallback"""

        with patch.object(mlflow.pyfunc, 'load_model') as mock_load:
            # Production fails, staging succeeds
            mock_load.side_effect = [Exception("Production failed"), Mock()]

            success = await model_manager.initialize()
            assert success
            assert model_manager.current_stage == "Staging"

    @pytest.mark.asyncio
    async def test_prediction_with_context(self, model_manager):
        """Test prediction with conversation context"""

        model_manager.model = Mock()
        model_manager.model.predict.return_value = ["Test response"]
        model_manager.current_version = "1"
        model_manager.current_stage = "Production"

        result = await model_manager.predict("Test query", {"context": "test"})

        assert result["response"] == "Test response"
        assert result["model_version"] == "1"
        assert "timestamp" in result

class TestFeedbackCollector:

    @pytest.fixture
    def feedback_collector(self, tmp_path):
        return StructuredFeedbackCollector(str(tmp_path))

    @pytest.mark.asyncio
    async def test_feedback_analysis(self, feedback_collector):
        """Test feedback analysis and categorization"""

        feedback = UserFeedback(
            query="Test query",
            response="Test response",
            rating=FeedbackRating.POOR,
            feedback_text="This answer is completely wrong and dangerous",
            model_version="1",
            session_id="test-session",
            user_id="test-user",
            timestamp=datetime.utcnow()
        )

        analyzed = await feedback_collector._analyze_feedback(feedback)

        assert analyzed.requires_immediate_attention
        assert ImprovementCategory.ACCURACY in analyzed.improvement_categories
        assert ImprovementCategory.SAFETY in analyzed.improvement_categories
```

### Integration Tests

```python
from fastapi.testclient import TestClient

class TestQueryEndpoint:

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_query_processing(self, client):
        """Test end-to-end query processing"""

        response = client.post("/v1/query", json={
            "query": "What's my average blood glucose?",
            "include_context": True
        })

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "model_version" in data
        assert "session_id" in data

    def test_feedback_submission(self, client):
        """Test feedback submission"""

        response = client.post("/v1/feedback", json={
            "query": "Test query",
            "response": "Test response",
            "rating": 4,
            "feedback_text": "Good response",
            "session_id": "test-session"
        })

        assert response.status_code == 200
        assert response.json()["message"] == "Feedback received successfully"
```

## Key Implementation Notes

1. **Safety First**: All model promotions require manual human approval
2. **Intelligent Feedback**: Structured analysis identifies clinical issues and improvement areas
3. **Conversation Context**: Maintains session-based conversation history for better responses
4. **Robust Fallbacks**: Production -> Staging -> Error hierarchy for model loading
5. **Comprehensive Monitoring**: Prometheus metrics and structured logging throughout
6. **Clinical Intelligence**: Feedback analysis considers clinical relevance and safety concerns

This implementation provides a production-ready AI query interface that balances intelligent features with operational safety and human oversight requirements.
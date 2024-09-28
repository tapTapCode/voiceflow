"""
Outbound Lead Generation Agent - Calls leads, qualifies them, and scores engagement.
"""

from typing import Optional, Dict, Any, List
from backend.core import LLMService, VoiceService, LeadMemory
from backend.outbound.models import (
    QualificationStatus,
    LeadStatus,
    CampaignStatus,
)
import json


class OutboundLeadAgent:
    """
    AI-powered outbound lead qualification agent.
    Makes calls to leads and qualifies them based on responses.
    """

    OPENING_SCRIPT = """Hi {lead_name}, this is {agent_name} calling from {company}. 
I noticed you work in {industry} and thought you might be interested in learning about how we help companies 
like yours {value_prop}. Do you have about 2 minutes to chat?"""

    QUALIFICATION_QUESTIONS = [
        "Are you currently looking for solutions in this area?",
        "What's your timeline for making a decision?",
        "Do you have budget allocated for this?",
        "Are you the decision maker for this?",
    ]

    FOLLOW_UP_INTENTS = [
        "callback",
        "schedule meeting",
        "send more info",
        "not interested",
        "already using",
        "budget",
        "timeline",
    ]

    def __init__(self):
        """Initialize outbound agent."""
        self.llm = LLMService()
        self.voice = VoiceService()
        self.memory = LeadMemory()

    async def start_lead_call(
        self,
        call_sid: str,
        lead_name: str,
        lead_phone: str,
        company: str,
        industry: str,
        value_prop: str,
        agent_name: str = "Sales Agent",
    ) -> str:
        """
        Start outbound call to lead.
        
        Args:
            call_sid: Twilio call SID
            lead_name: Lead first name
            lead_phone: Lead phone number
            company: Company calling from
            industry: Lead's industry
            value_prop: Value proposition to mention
            agent_name: Agent name to use in greeting
            
        Returns:
            Initial greeting message
        """
        # Format opening script
        opening = self.OPENING_SCRIPT.format(
            lead_name=lead_name,
            agent_name=agent_name,
            company=company,
            industry=industry,
            value_prop=value_prop,
        )
        
        # Initialize conversation memory for this lead
        context = {
            "lead_name": lead_name,
            "phone": lead_phone,
            "company": company,
            "industry": industry,
        }
        self.memory.start_conversation(call_sid, context)
        
        # Synthesize to speech
        audio = await self.voice.synthesize(opening)
        
        return opening

    async def ask_qualification_question(
        self,
        call_sid: str,
        question_index: int,
    ) -> str:
        """
        Ask next qualification question.
        
        Args:
            call_sid: Call SID
            question_index: Index of question to ask (0-3)
            
        Returns:
            Question text
        """
        if question_index >= len(self.QUALIFICATION_QUESTIONS):
            return "Thank you for your time. We'll follow up with you soon!"
        
        question = self.QUALIFICATION_QUESTIONS[question_index]
        
        # Synthesize question
        audio = await self.voice.synthesize(question)
        
        return question

    async def process_lead_response(
        self,
        call_sid: str,
        lead_response: str,
        question_index: int,
    ) -> Dict[str, Any]:
        """
        Process lead's response and decide next action.
        
        Args:
            call_sid: Call SID
            lead_response: Lead's spoken response
            question_index: Current question index
            
        Returns:
            Response with next action and qualification data
        """
        # Add response to memory
        self.memory.track_lead_data(
            call_sid,
            f"q{question_index}_response",
            lead_response,
        )
        
        # Extract intent/sentiment
        intent = await self.llm.extract_intent(
            lead_response,
            self.FOLLOW_UP_INTENTS + ["yes", "no", "maybe", "interested", "not interested"],
        )
        
        # Score this response
        score = await self._score_response(question_index, lead_response, intent)
        
        # Determine next action
        next_action = "continue"  # continue, end_call, schedule_callback
        
        if intent in ["not interested", "already using"]:
            next_action = "end_call_polite"
        elif intent in ["callback", "schedule meeting"]:
            next_action = "schedule_callback"
        
        return {
            "intent": intent,
            "score": score,
            "next_action": next_action,
            "next_question": question_index + 1 if next_action == "continue" else None,
        }

    async def end_lead_call(
        self,
        call_sid: str,
        duration_seconds: int,
        transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        End call and calculate lead qualification.
        
        Args:
            call_sid: Call SID
            duration_seconds: Call duration
            transcript: Full call transcript
            
        Returns:
            Qualification result and recommended action
        """
        # Get lead profile from memory
        lead_profile = self.memory.get_lead_profile(call_sid)
        
        # Calculate final score
        qualification = await self._calculate_qualification(
            call_sid,
            lead_profile,
            transcript,
        )
        
        # End conversation
        summary = self.memory.end_conversation(call_sid)
        summary.update({
            "duration_seconds": duration_seconds,
            "transcript": transcript,
            "qualification": qualification,
        })
        
        return summary

    async def generate_follow_up_message(
        self,
        call_sid: str,
        follow_up_type: str,
    ) -> str:
        """
        Generate follow-up message based on call result.
        
        Args:
            call_sid: Call SID
            follow_up_type: Type of follow-up (callback, email, meeting)
            
        Returns:
            Follow-up message
        """
        lead_name = self.memory.get_context(call_sid).get("lead_name", "there")
        
        if follow_up_type == "callback":
            return f"Perfect {lead_name}! We'll give you a call back next week. Thanks for your time!"
        elif follow_up_type == "email":
            return f"Great to chat with you, {lead_name}. I'll send over some more information. Look for it in your inbox!"
        elif follow_up_type == "meeting":
            return f"Fantastic, {lead_name}! Let's schedule a time to dive deeper. I'll send you a calendar invite!"
        else:
            return f"Thanks for your time, {lead_name}. We appreciate you!"

    async def _score_response(
        self,
        question_index: int,
        response: str,
        intent: str,
    ) -> float:
        """
        Score individual response (0-100).
        
        Args:
            question_index: Question index (0-3)
            response: Lead's response
            intent: Detected intent
            
        Returns:
            Score 0-100
        """
        score = 50  # Neutral starting point
        
        # Scoring by question type
        if question_index == 0:  # Interest
            if intent in ["yes", "interested", "maybe"]:
                score = 75
            elif intent in ["not interested", "no"]:
                score = 25
                
        elif question_index == 1:  # Timeline
            if intent in ["asap", "immediate", "soon"]:
                score = 85
            elif intent in ["6+ months", "not sure", "no"]:
                score = 30
                
        elif question_index == 2:  # Budget
            if intent in ["yes", "yes", "approved"]:
                score = 90
            elif intent in ["no", "not yet", "no budget"]:
                score = 20
                
        elif question_index == 3:  # Authority
            if intent in ["yes", "decision maker", "approve"]:
                score = 95
            elif intent in ["no", "need approval", "not mine"]:
                score = 40
        
        return score

    async def _calculate_qualification(
        self,
        call_sid: str,
        lead_profile: Dict,
        transcript: Optional[str],
    ) -> Dict[str, Any]:
        """
        Calculate final lead qualification.
        
        Args:
            call_sid: Call SID
            lead_profile: Lead profile data from memory
            transcript: Call transcript
            
        Returns:
            Qualification data with score and status
        """
        # Use LLM to analyze overall fit
        analysis = await self.llm.lead_score({
            "responses": lead_profile.get("lead_data", {}),
            "duration": lead_profile.get("engagement_score", 0),
            "sentiment": lead_profile.get("sentiment", "neutral"),
            "budget": "Yes" if lead_profile.get("lead_data", {}).get("has_budget") else "No",
            "timeline": lead_profile.get("lead_data", {}).get("timeline", "Unknown"),
        })
        
        # Map to qualification status
        score = analysis.get("score", 50)
        if score >= 75:
            status = QualificationStatus.HOT
        elif score >= 50:
            status = QualificationStatus.WARM
        elif score >= 25:
            status = QualificationStatus.COLD
        else:
            status = QualificationStatus.DISQUALIFIED
        
        return {
            "score": score,
            "status": status.value,
            "qualified": analysis.get("qualified", False),
            "reasons": analysis.get("reasons", []),
            "recommended_action": self._get_recommended_action(score, status),
        }

    def _get_recommended_action(
        self,
        score: float,
        status: QualificationStatus,
    ) -> str:
        """
        Get recommended follow-up action.
        
        Args:
            score: Qualification score
            status: Qualification status
            
        Returns:
            Recommended action
        """
        if status == QualificationStatus.HOT:
            return "schedule_meeting"
        elif status == QualificationStatus.WARM:
            return "send_info"
        elif status == QualificationStatus.COLD:
            return "callback"
        else:
            return "archive"

    def _get_call_quality_score(self, lead_profile: Dict) -> float:
        """
        Calculate call quality score (0-100).
        
        Args:
            lead_profile: Lead profile data
            
        Returns:
            Quality score
        """
        score = lead_profile.get("engagement_score", 50)
        
        # Boost for positive sentiment
        if lead_profile.get("sentiment") == "positive":
            score += 15
        elif lead_profile.get("sentiment") == "negative":
            score -= 15
        
        return min(max(score, 0), 100)

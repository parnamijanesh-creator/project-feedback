"""AI-Assisted Thematic Card Clustering Service using structured LLM output."""
import logging
import os
from typing import List, Optional
from django.conf import settings
from django.db import transaction
from pydantic import BaseModel, Field

from apps.cycles.models import FeedbackCard
from apps.retrospectives.models import RetrospectiveSession, TopicCluster

logger = logging.getLogger(__name__)


class ThematicClusterItem(BaseModel):
    """Pydantic model representing an individual thematic cluster."""

    title: str = Field(description="Descriptive title of the cluster, 2-5 words")
    description: str = Field(default="", description="Summary of the shared theme across these cards")
    card_ids: List[int] = Field(description="List of integer card IDs belonging to this cluster")


class ClusteringResponse(BaseModel):
    """Guaranteed structured output response from LLM."""

    clusters: List[ThematicClusterItem] = Field(
        default_factory=list,
        description="List of thematic clusters grouping the provided cards",
    )


SYSTEM_PROMPT = """You are an agile retrospective facilitator.
Your job is to group team feedback cards (Start, Stop, Continue) into cohesive thematic clusters.
Group related feedback cards together. Give each cluster a clear, action-oriented title (2-5 words) and a concise summary.
Ensure every card_id in each cluster matches one of the provided card IDs. Do not invent new card IDs.
If a card is unique and does not fit any theme, leave it out of clusters."""


class AIClusteringService:
    """Service to group retrospective feedback cards into thematic clusters via LLM."""

    def __init__(self, client=None, model: str = "gpt-4o-mini"):
        self._client = client
        self.model = model

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
            self._client = OpenAI(api_key=api_key or "sk-dummy-key-for-test-init")
        return self._client

    def cluster_session(self, session: RetrospectiveSession) -> List[TopicCluster]:
        """Clusters revealed cards for a retrospective session using structured LLM output.

        Returns a list of created TopicCluster records, or [] on skip or error.
        """
        cards = list(session.cycle.cards.all())

        # Skip LLM call if fewer than 2 cards
        if len(cards) < 2:
            logger.info(
                "Cycle %s has %d cards (fewer than 2). Skipping AI clustering.",
                session.cycle.pk,
                len(cards),
            )
            return []

        valid_card_ids = {card.pk for card in cards}

        # Build prompt listing the cards
        card_descriptions = [
            f"Card ID {card.pk} | [{card.get_category_display()}]: {card.text.strip()}"
            for card in cards
        ]
        user_prompt = "Here are the team feedback cards to cluster:\n\n" + "\n".join(card_descriptions)

        # Call LLM with guaranteed structured output
        try:
            parsed_response = self._call_llm(user_prompt)
        except Exception as e:
            logger.error(
                "AI clustering LLM call failed for session %s (cycle %s): %s",
                session.pk,
                session.cycle.pk,
                str(e),
                exc_info=True,
            )
            return []

        if not parsed_response or not parsed_response.clusters:
            logger.info("LLM returned no clusters for session %s.", session.pk)
            return []

        # Create clusters and associate valid cards inside transaction
        created_clusters: List[TopicCluster] = []

        with transaction.atomic():
            # Reset previous cluster associations on cards for this cycle
            FeedbackCard.objects.filter(cycle=session.cycle).update(cluster=None)
            # Remove previous AI-generated clusters for this session
            session.clusters.filter(is_ai_generated=True).delete()

            for cluster_data in parsed_response.clusters:
                # Sanitize card IDs: only keep IDs belonging to this active cycle
                matching_card_ids = [
                    cid for cid in cluster_data.card_ids if cid in valid_card_ids
                ]
                if not matching_card_ids:
                    continue

                topic_cluster = TopicCluster.objects.create(
                    session=session,
                    title=cluster_data.title[:255],
                    description=cluster_data.description,
                    is_ai_generated=True,
                )
                FeedbackCard.objects.filter(
                    id__in=matching_card_ids, cycle=session.cycle
                ).update(cluster=topic_cluster)

                created_clusters.append(topic_cluster)

            if created_clusters:
                session.current_stage = RetrospectiveSession.Stage.CLUSTER
                session.save(update_fields=["current_stage"])

        return created_clusters

    def _call_llm(self, user_prompt: str) -> ClusteringResponse:
        """Invokes LLM with structured output format."""
        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ClusteringResponse,
        )
        return completion.choices[0].message.parsed

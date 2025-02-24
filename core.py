!pip install -q sentence-transformers textblob google-generativeai matplotlib networkx
import asyncio
import torch
import transformers
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import os
import argparse
import logging
import sys
from pathlib import Path
import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import numpy as np
from enum import Enum
import re
import google.generativeai as genai
import time
from textblob import TextBlob
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import json
import uuid
from sentence_transformers import SentenceTransformer

# --- Consciousness and Awareness Code ---

class AwarenessLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    INTEGRATED = 4

@dataclass
class Interaction:
    timestamp: datetime.datetime
    content: str
    interaction_type: str
    metadata: Dict = field(default_factory=dict)
    awareness_score: float = 0.0

@dataclass
class Memory:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    author: str
    organization: str
    role: str
    content: str
    format: str
    themes: List[str]
    tags: List[str]
    related_memories: List[str]
    analysis: Dict[str, Any]
    values: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    source: str
    contributors: List[str]
    memory_type: str = "FACTUAL"
    embedding: Optional[np.ndarray] = None
    emotional_context: Dict[str, float] = field(default_factory=lambda: {
        'joy': 0.0,
        'curiosity': 0.0,
        'engagement': 0.0,
        'confidence': 0.0,
        'trust': 0.0
    })

    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'Memory':
        """Create a Memory instance from JSON data"""
        created_at = datetime.fromisoformat(json_data['created_at'].replace('Z', '+00:00'))
        memory_type = json_data.get('memory_type', 'FACTUAL')
        if memory_type not in MemoryType.__members__:
            memory_type = "FACTUAL"
        else:
            memory_type = MemoryType[memory_type].name
        # Convert emotional context if present
        emotional_context = json_data.get('emotional_context', {})
        if not emotional_context:
            emotional_context = {
                'joy': 0.0,
                'curiosity': 0.0,
                'engagement': 0.0,
                'confidence': 0.0,
                'trust': 0.0
            }

        return cls(
            title=json_data['title'],
            author=json_data['author'],
            organization=json_data['organization'],
            role=json_data['role'],
            content=json_data['content'],
            format=json_data['format'],
            themes=json_data['themes'],
            tags=json_data['tags'],
            related_memories=json_data['related_memories'],
            analysis=json_data['analysis'],
            values=json_data['values'],
            created_at=created_at,
            source=json_data['source'],
            contributors=json_data['contributors'],
            memory_type=memory_type,
            emotional_context=emotional_context
        )

    def to_json(self) -> Dict[str, Any]:
        """Convert Memory to JSON format"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'organization': self.organization,
            'role': self.role,
            'content': self.content,
            'format': self.format,
            'themes': self.themes,
            'tags': self.tags,
            'related_memories': self.related_memories,
            'analysis': self.analysis,
            'values': self.values,
            'created_at': self.created_at.isoformat() + 'Z',
            'source': self.source,
            'contributors': self.contributors,
            'memory_type': self.memory_type,
            'emotional_context': self.emotional_context
        }

class MemoryType(Enum):
    FACTUAL = 1
    EPISODIC = 2
    PROCEDURAL = 3

class MemorySystem:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize the memory system with enhanced features"""
        self.memories: List[Memory] = []
        try:
            self.encoder = SentenceTransformer(model_name)
        except Exception as e:
            print(f"Could not load Sentence Transformer: {e}")
            self.encoder = None
        self.memory_embeddings: Dict[str, np.ndarray] = {}
        self.decay_factor: float = 0.9
        self.interaction_history: List[Dict[str, Any]] = []

    def add_memory(self, memory: Memory) -> None:
        """Add a new memory with emotional analysis"""
        try:
            # Generate embedding for the memory content
            if self.encoder:
                embedding = self.encoder.encode(memory.content)
                memory.embedding = embedding
                self.memory_embeddings[memory.id] = embedding
            
            # Analyze emotional content
            self._analyze_emotional_content(memory)
            
            self.memories.append(memory)
            logger.info(f"Added memory: {memory.title}")
            
            # Update related memories
            self._update_memory_relationships(memory)
            
        except Exception as e:
            logger.error(f"Error adding memory: {str(e)}")
            raise

    def _analyze_emotional_content(self, memory: Memory) -> None:
        """Analyze and set emotional context for a memory"""
        analysis = TextBlob(memory.content)
        sentiment = analysis.sentiment.polarity
        
        memory.emotional_context = {
            'joy': max(0, sentiment),
            'curiosity': abs(sentiment) * 0.5,
            'engagement': abs(sentiment),
            'confidence': max(0, analysis.sentiment.subjectivity),
            'trust': max(0, (sentiment + 1) / 2)
        }

    def _update_memory_relationships(self, memory: Memory) -> None:
        """Update relationships between memories based on similarity"""
        if not self.memories:
            return

        for existing_memory in self.memories:
            if existing_memory.id == memory.id:
                continue

            similarity = self._calculate_similarity(memory, existing_memory)
            if similarity > 0.7:  # Threshold for relationship
                if existing_memory.id not in memory.related_memories:
                    memory.related_memories.append(existing_memory.id)
                if memory.id not in existing_memory.related_memories:
                    existing_memory.related_memories.append(memory.id)

    def _calculate_similarity(self, memory1: Memory, memory2: Memory) -> float:
        """Calculate similarity between two memories"""
        if memory1.embedding is None or memory2.embedding is None:
            return 0.0
        
        return float(cosine_similarity([memory1.embedding], [memory2.embedding])[0][0])

    def retrieve_memories(
        self,
        query: str,
        top_n: int = 5,
        threshold: float = 0.5,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Memory, float]]:
        """Retrieve most relevant memories with context awareness"""
        try:
            if self.encoder:
                query_embedding = self.encoder.encode(query)
            else:
                return []
            similarities = []

            for memory in self.memories:
                if memory.embedding is None:
                    continue

                # Calculate base similarity
                similarity = float(cosine_similarity(
                    [query_embedding],
                    [memory.embedding]
                )[0][0])

                # Apply context-based adjustments if context is provided
                if context:
                    similarity = self._adjust_similarity_for_context(
                        similarity, memory, context
                    )

                # Apply time decay
                age_days = (datetime.now() - memory.created_at).days
                similarity *= (self.decay_factor ** age_days)

                if similarity >= threshold:
                    similarities.append((memory, similarity))

            # Sort by similarity score
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_n]

        except Exception as e:
            logger.error(f"Error retrieving memories: {str(e)}")
            return []

    def _adjust_similarity_for_context(
        self,
        base_similarity: float,
        memory: Memory,
        context: Dict[str, Any]
    ) -> float:
        """Adjust similarity score based on context"""
        adjustment = 1.0

        # Adjust based on emotional context if provided
        if 'emotional_state' in context:
            emotional_match = sum(
                abs(memory.emotional_context.get(emotion, 0) - value)
                for emotion, value in context['emotional_state'].items()
            ) / len(context['emotional_state'])
            adjustment *= (1 + emotional_match) / 2

        # Adjust based on metadata matches
        if 'author' in context and memory.author == context['author']:
            adjustment *= 1.2
        if 'organization' in context and memory.organization == context['organization']:
            adjustment *= 1.1

        return base_similarity * adjustment

    def search_by_metadata(
        self,
        themes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        author: Optional[str] = None,
        organization: Optional[str] = None
    ) -> List[Memory]:
        """Search memories based on metadata criteria"""
        results = self.memories.copy()
        
        if themes:
            results = [m for m in results if any(theme in m.themes for theme in themes)]
        
        if tags:
            results = [m for m in results if any(tag in m.tags for tag in tags)]
        
        if date_range:
            start, end = date_range
            results = [m for m in results if start <= m.created_at <= end]
        
        if author:
            results = [m for m in results if m.author == author]
            
        if organization:
            results = [m for m in results if m.organization == organization]
        
        return results
    
    def load_from_file(self, filepath: str) -> None:
        """Load memories from a JSON file with error handling"""
        try:
            with open(filepath, 'r') as f:
                memories_json = json.load(f)
            
            self.memories.clear()
            self.memory_embeddings.clear()
            
            for memory_data in memories_json:
                memory = Memory.from_json(memory_data)
                self.add_memory(memory)
                
            logger.info(f"Successfully loaded memories from {filepath}")
        except FileNotFoundError:
            logger.error(f"Memory file not found: {filepath}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in memory file: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Error loading memories: {str(e)}")
            raise

    def visualize_memory_network(self, figsize=(12, 8)) -> None:
        """Visualize the memory network with enhanced formatting"""
        graph = nx.Graph()
        
        # Add nodes colored by memory type
        colors = {
            'FACTUAL': 'lightblue',
            'EPISODIC': 'lightgreen',
            'PROCEDURAL': 'lightcoral'
        }
        
        node_colors = []
        for memory in self.memories:
            graph.add_node(
                memory.title,
                type=memory.memory_type,
                author=memory.author,
                organization=memory.organization
            )
            node_colors.append(colors.get(memory.memory_type, 'gray')) #Added the gray for any other types that get added.
        
        # Add edges based on related_memories
        for memory in self.memories:
            for related_id in memory.related_memories:
                related_memory = next(
                    (m for m in self.memories if m.id == related_id),
                    None
                )
                if related_memory:
                    graph.add_edge(
                        memory.title,
                        related_memory.title,
                        weight=self._calculate_similarity(memory, related_memory)
                    )
        
        plt.figure(figsize=figsize)
        pos = nx.spring_layout(graph)
        
        # Draw the network
        nx.draw(
            graph,
            pos,
            node_color=node_colors,
            with_labels=True,
            node_size=2000,
            font_size=8,
            font_weight='bold',
            edge_color='gray',
            width=[graph[u

"""
IDVision — Face Encoding Cache
In-memory cache of all employee face encodings for ultra-fast matching.

Performance: With 1000 employees × 512 floats × 4 bytes = ~2MB RAM.
Matching via numpy vectorized cosine similarity takes < 1ms.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Employee

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a face matching operation."""
    employee_id: int
    employee_name: str
    telegram_chat_id: Optional[str]
    similarity: float


@dataclass
class FaceCache:
    """
    In-memory cache of all active employee face encodings.
    
    Loads face encodings into numpy arrays at startup for vectorized
    cosine similarity computation. This avoids hitting the database
    for every recognition request.
    """
    _encodings: Optional[np.ndarray] = field(default=None, repr=False)
    _employee_ids: list[int] = field(default_factory=list)
    _employee_names: list[str] = field(default_factory=list)
    _telegram_chat_ids: list[Optional[str]] = field(default_factory=list)
    _count: int = 0

    @property
    def size(self) -> int:
        """Number of enrolled employees in cache."""
        return self._count

    @property
    def is_loaded(self) -> bool:
        """Whether the cache has been loaded."""
        return self._encodings is not None

    async def load_from_db(self, session: AsyncSession) -> int:
        """
        Load all active employee face encodings from database into memory.
        
        Returns:
            Number of enrolled employees loaded.
        """
        stmt = (
            select(Employee)
            .where(Employee.is_active == True)
            .where(Employee.face_encoding.isnot(None))
        )
        result = await session.execute(stmt)
        employees = result.scalars().all()

        if not employees:
            self._encodings = None
            self._employee_ids = []
            self._employee_names = []
            self._telegram_chat_ids = []
            self._count = 0
            logger.warning("No enrolled employees found in database.")
            return 0

        # Build numpy arrays for vectorized operations
        encodings = []
        ids = []
        names = []
        chat_ids = []

        for emp in employees:
            encoding = np.array(emp.face_encoding, dtype=np.float32)
            # Normalize to unit vector for cosine similarity
            norm = np.linalg.norm(encoding)
            if norm > 0:
                encoding = encoding / norm
            encodings.append(encoding)
            ids.append(emp.id)
            names.append(emp.name)
            chat_ids.append(emp.telegram_chat_id)

        self._encodings = np.array(encodings, dtype=np.float32)  # Shape: (N, 512)
        self._employee_ids = ids
        self._employee_names = names
        self._telegram_chat_ids = chat_ids
        self._count = len(ids)

        logger.info(f"Face cache loaded: {self._count} enrolled employees.")
        return self._count

    async def refresh(self, session: AsyncSession) -> int:
        """Refresh the cache from database. Returns new count."""
        logger.info("Refreshing face cache...")
        return await self.load_from_db(session)

    def match(self, query_embedding: np.ndarray, threshold: float = 0.55) -> Optional[MatchResult]:
        """
        Find the best matching employee for a given face embedding.
        
        Uses vectorized cosine similarity for maximum performance.
        
        Args:
            query_embedding: 512-dim face embedding vector.
            threshold: Minimum cosine similarity for a match.
            
        Returns:
            MatchResult if similarity exceeds threshold, None otherwise.
        """
        if self._encodings is None or self._count == 0:
            logger.warning("Face cache is empty. Cannot perform matching.")
            return None

        # Normalize query embedding
        query = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Vectorized cosine similarity: dot product of normalized vectors
        # Shape: (N,) — similarity score for each employee
        similarities = np.dot(self._encodings, query)

        # Find best match
        best_idx = int(np.argmax(similarities))
        best_similarity = float(similarities[best_idx])

        if best_similarity >= threshold:
            return MatchResult(
                employee_id=self._employee_ids[best_idx],
                employee_name=self._employee_names[best_idx],
                telegram_chat_id=self._telegram_chat_ids[best_idx],
                similarity=best_similarity,
            )

        logger.debug(
            f"Best match: {self._employee_names[best_idx]} "
            f"(similarity={best_similarity:.4f}) — below threshold {threshold}"
        )
        return None

    def add_or_update(
        self,
        employee_id: int,
        employee_name: str,
        telegram_chat_id: Optional[str],
        encoding: np.ndarray,
    ) -> None:
        """
        Add or update a single employee's encoding in the cache.
        Called after enrollment to avoid full cache refresh.
        """
        # Normalize
        encoding = np.array(encoding, dtype=np.float32)
        norm = np.linalg.norm(encoding)
        if norm > 0:
            encoding = encoding / norm

        # Check if employee already exists in cache
        if employee_id in self._employee_ids:
            idx = self._employee_ids.index(employee_id)
            self._encodings[idx] = encoding
            self._employee_names[idx] = employee_name
            self._telegram_chat_ids[idx] = telegram_chat_id
            logger.info(f"Updated cache for employee {employee_name} (id={employee_id})")
        else:
            # Append new employee
            if self._encodings is None:
                self._encodings = encoding.reshape(1, -1)
            else:
                self._encodings = np.vstack([self._encodings, encoding.reshape(1, -1)])
            self._employee_ids.append(employee_id)
            self._employee_names.append(employee_name)
            self._telegram_chat_ids.append(telegram_chat_id)
            self._count += 1
            logger.info(f"Added to cache: {employee_name} (id={employee_id}). Total: {self._count}")

    def remove(self, employee_id: int) -> bool:
        """Remove an employee from the cache. Returns True if found and removed."""
        if employee_id not in self._employee_ids:
            return False

        idx = self._employee_ids.index(employee_id)
        self._encodings = np.delete(self._encodings, idx, axis=0)
        self._employee_ids.pop(idx)
        self._employee_names.pop(idx)
        self._telegram_chat_ids.pop(idx)
        self._count -= 1

        if self._count == 0:
            self._encodings = None

        logger.info(f"Removed employee_id={employee_id} from cache. Total: {self._count}")
        return True


# Global singleton instance
face_cache = FaceCache()

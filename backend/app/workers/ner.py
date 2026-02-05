"""NER (Named Entity Recognition) worker for extracting vocabulary and entities."""

import re
from collections import Counter
from typing import List, Optional, Set
from loguru import logger

from app.models.card import (
    EntityType,
    WordAnnotation,
    EntityAnnotation,
    SegmentAnnotations,
    TimelineAnnotations,
)
from app.models.timeline import Timeline

# Common English words to skip (stop words + very common words)
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "dare", "ought", "used", "it", "its", "it's", "i", "me",
    "my", "mine", "we", "us", "our", "ours", "you", "your", "yours", "he", "him", "his",
    "she", "her", "hers", "they", "them", "their", "theirs", "what", "which", "who",
    "whom", "this", "that", "these", "those", "am", "isn't", "aren't", "wasn't",
    "weren't", "hasn't", "haven't", "hadn't", "doesn't", "don't", "didn't", "won't",
    "wouldn't", "shan't", "shouldn't", "can't", "cannot", "couldn't", "mustn't",
    "let's", "that's", "who's", "what's", "here's", "there's", "when's", "where's",
    "why's", "how's", "because", "just", "only", "own", "same", "so", "than", "too",
    "very", "s", "t", "just", "now", "then", "well", "also", "back", "even", "still",
    "way", "such", "both", "each", "few", "more", "most", "other", "some", "any",
    "no", "nor", "not", "only", "over", "under", "again", "further", "once", "here",
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "yeah", "yes", "okay", "ok", "um", "uh",
    "like", "know", "think", "want", "get", "go", "going", "got", "come", "coming",
    "came", "make", "made", "take", "took", "see", "saw", "look", "looking", "give",
    "gave", "find", "found", "tell", "told", "say", "said", "keep", "kept", "let",
    "put", "seem", "seemed", "leave", "left", "call", "called", "being", "having",
    "doing", "getting", "making", "taking", "seeing", "giving", "finding", "telling",
    "saying", "keeping", "putting", "leaving", "calling", "really", "actually",
    "probably", "maybe", "something", "anything", "everything", "nothing", "someone",
    "anyone", "everyone", "nobody", "thing", "things", "people", "person", "time",
    "times", "day", "days", "year", "years", "right", "good", "new", "first", "last",
    "long", "great", "little", "own", "other", "old", "right", "big", "high", "different",
    "small", "large", "next", "early", "young", "important", "few", "public", "bad",
    "same", "able", "mr", "mrs", "ms", "dr", "gonna", "wanna", "gotta", "kinda",
    "sorta", "lemme", "gimme",
}

# Common word frequency threshold (words more common than this are skipped)
# Based on Corpus of Contemporary American English (COCA) frequency rank
FREQUENCY_THRESHOLD = 3000


class NERWorker:
    """Worker for Named Entity Recognition and vocabulary extraction.

    Uses rule-based approach for vocabulary extraction and
    optionally spaCy or OpenAI for entity recognition.
    """

    def __init__(self, use_spacy: bool = True, spacy_model: str = "en_core_web_sm"):
        """Initialize NER worker.

        Args:
            use_spacy: Whether to use spaCy for NER.
            spacy_model: spaCy model to use.
        """
        self.use_spacy = use_spacy
        self.nlp = None

        if use_spacy:
            try:
                import spacy
                self.nlp = spacy.load(spacy_model)
                logger.info(f"Loaded spaCy model: {spacy_model}")
            except Exception as e:
                logger.warning(f"Failed to load spaCy: {e}. Using rule-based extraction only.")
                self.use_spacy = False

    def process_segment(
        self,
        segment_id: int,
        text: str,
        extract_vocabulary: bool = True,
        extract_entities: bool = True,
    ) -> SegmentAnnotations:
        """Process a single segment and extract vocabulary and entities.

        Args:
            segment_id: ID of the segment.
            text: English text to process.
            extract_vocabulary: Whether to extract vocabulary words.
            extract_entities: Whether to extract named entities.

        Returns:
            SegmentAnnotations with extracted data.
        """
        words = self._extract_vocabulary(text) if extract_vocabulary else []
        entities = self._extract_entities(text) if extract_entities else []

        annotation = SegmentAnnotations(
            segment_id=segment_id,
            words=words,
            entities=entities,
        )

        logger.debug(
            f"Processed segment {segment_id}: "
            f"{len(words)} words, {len(entities)} entities"
        )

        return annotation

    def process_timeline(
        self,
        timeline: Timeline,
        extract_vocabulary: bool = True,
        extract_entities: bool = True,
        vocabulary_limit: int = 50,
        entity_limit: int = 20,
    ) -> TimelineAnnotations:
        """Process a timeline and extract vocabulary and entities.

        Args:
            timeline: Timeline to process.
            extract_vocabulary: Whether to extract vocabulary words.
            extract_entities: Whether to extract named entities.
            vocabulary_limit: Max vocabulary words to return.
            entity_limit: Max entities to return.

        Returns:
            TimelineAnnotations with extracted data.
        """
        all_text = ""
        segment_annotations = []

        # Process each segment
        for segment in timeline.segments:
            text = segment.en  # English text

            # Extract from this segment
            words = self._extract_vocabulary(text) if extract_vocabulary else []
            entities = self._extract_entities(text) if extract_entities else []

            annotation = SegmentAnnotations(
                segment_id=segment.id,
                words=words,
                entities=entities,
            )
            segment_annotations.append(annotation)
            all_text += " " + text

        # Aggregate unique words and entities
        word_counter = Counter()
        entity_set: Set[str] = set()

        for seg_ann in segment_annotations:
            for word in seg_ann.words:
                word_counter[word.lemma] += 1
            for entity in seg_ann.entities:
                if entity.entity_id:
                    entity_set.add(entity.entity_id)
                else:
                    entity_set.add(entity.text)

        # Sort words by frequency and take top N
        unique_words = [w for w, _ in word_counter.most_common(vocabulary_limit)]
        unique_entities = list(entity_set)[:entity_limit]

        annotations = TimelineAnnotations(
            timeline_id=timeline.timeline_id,
            segments=segment_annotations,
            unique_words=unique_words,
            unique_entities=unique_entities,
            model_used="spacy" if self.use_spacy else "rule_based",
        )

        logger.info(
            f"Processed timeline {timeline.timeline_id}: "
            f"{len(unique_words)} words, {len(unique_entities)} entities"
        )

        return annotations

    def _extract_vocabulary(self, text: str) -> List[WordAnnotation]:
        """Extract vocabulary words from text.

        Uses tokenization and filters to extract learnable vocabulary.

        Args:
            text: Text to process.

        Returns:
            List of WordAnnotation.
        """
        words = []

        if self.nlp:
            # Use spaCy for better tokenization and lemmatization
            doc = self.nlp(text)
            for token in doc:
                if self._is_vocabulary_word(token.text, token.lemma_, token.pos_):
                    words.append(WordAnnotation(
                        word=token.text,
                        lemma=token.lemma_.lower(),
                        start_char=token.idx,
                        end_char=token.idx + len(token.text),
                        is_vocabulary=True,
                    ))
        else:
            # Rule-based tokenization
            pattern = r'\b[a-zA-Z]+(?:\'[a-zA-Z]+)?\b'
            for match in re.finditer(pattern, text):
                word = match.group()
                lemma = word.lower()  # Simple lemmatization
                if self._is_vocabulary_word(word, lemma):
                    words.append(WordAnnotation(
                        word=word,
                        lemma=lemma,
                        start_char=match.start(),
                        end_char=match.end(),
                        is_vocabulary=True,
                    ))

        return words

    def _is_vocabulary_word(
        self,
        word: str,
        lemma: str,
        pos: Optional[str] = None,
    ) -> bool:
        """Check if a word should be included as vocabulary.

        Args:
            word: Original word form.
            lemma: Lemmatized form.
            pos: Part of speech (if available).

        Returns:
            True if word should be included.
        """
        # Skip short words
        if len(word) < 3:
            return False

        # Skip stop words
        if lemma.lower() in STOP_WORDS:
            return False

        # Skip words with numbers
        if any(c.isdigit() for c in word):
            return False

        # Skip all-caps (likely acronyms)
        if word.isupper() and len(word) > 2:
            return False

        # Skip if part of speech suggests it's not a content word
        if pos and pos in {"PUNCT", "SPACE", "X", "SYM", "NUM"}:
            return False

        return True

    def _extract_entities(self, text: str) -> List[EntityAnnotation]:
        """Extract named entities from text.

        Args:
            text: Text to process.

        Returns:
            List of EntityAnnotation.
        """
        entities = []

        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                entity_type = self._map_spacy_label_to_type(ent.label_)
                if entity_type:
                    entities.append(EntityAnnotation(
                        text=ent.text,
                        entity_type=entity_type,
                        start_char=ent.start_char,
                        end_char=ent.end_char,
                        confidence=0.8,  # spaCy doesn't provide confidence
                    ))
        else:
            # Simple rule-based: look for capitalized words
            pattern = r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b'
            for match in re.finditer(pattern, text):
                # Skip if at start of sentence (might just be capitalization)
                if match.start() > 0 and text[match.start() - 1] not in ".!?\n":
                    entities.append(EntityAnnotation(
                        text=match.group(),
                        entity_type=EntityType.OTHER,
                        start_char=match.start(),
                        end_char=match.end(),
                        confidence=0.5,
                    ))

        return entities

    def _map_spacy_label_to_type(self, label: str) -> Optional[EntityType]:
        """Map spaCy NER label to EntityType.

        Args:
            label: spaCy NER label.

        Returns:
            EntityType or None if not relevant.
        """
        mapping = {
            "PERSON": EntityType.PERSON,
            "PER": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "GPE": EntityType.PLACE,  # Geo-political entity (countries, cities)
            "LOC": EntityType.PLACE,  # Non-GPE locations
            "FAC": EntityType.PLACE,  # Facilities
            "EVENT": EntityType.EVENT,
            "WORK_OF_ART": EntityType.WORK,
            "PRODUCT": EntityType.PRODUCT,
            "NORP": EntityType.CONCEPT,  # Nationalities, religious groups
            "LAW": EntityType.CONCEPT,
        }
        return mapping.get(label)

    def extract_vocabulary_simple(self, text: str, limit: int = 50) -> List[str]:
        """Simple vocabulary extraction without annotations.

        Args:
            text: Text to process.
            limit: Max words to return.

        Returns:
            List of vocabulary words (lemmas).
        """
        word_counter = Counter()

        if self.nlp:
            doc = self.nlp(text)
            for token in doc:
                if self._is_vocabulary_word(token.text, token.lemma_, token.pos_):
                    word_counter[token.lemma_.lower()] += 1
        else:
            pattern = r'\b[a-zA-Z]{3,}\b'
            for match in re.finditer(pattern, text):
                word = match.group().lower()
                if word not in STOP_WORDS:
                    word_counter[word] += 1

        return [w for w, _ in word_counter.most_common(limit)]

    def extract_entities_simple(self, text: str, limit: int = 20) -> List[str]:
        """Simple entity extraction without annotations.

        Args:
            text: Text to process.
            limit: Max entities to return.

        Returns:
            List of entity surface forms.
        """
        entity_counter = Counter()

        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if self._map_spacy_label_to_type(ent.label_):
                    entity_counter[ent.text] += 1
        else:
            pattern = r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b'
            for match in re.finditer(pattern, text):
                entity_counter[match.group()] += 1

        return [e for e, _ in entity_counter.most_common(limit)]

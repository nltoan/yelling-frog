"""
Content Analyzer
Analyzes page content: word count, text ratio, readability, duplicate detection
"""
from typing import Dict, List, Optional, Any, Set
from bs4 import BeautifulSoup
import re
import hashlib


class ContentAnalyzer:
    """Analyze page content for SEO metrics"""

    def __init__(self):
        self.content_hashes = {}  # URL -> hash mapping
        self.content_similarity_cache = {}  # Cache for similarity calculations

    def extract_content_metrics(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract all content metrics

        Returns:
            - word_count: Words inside body tag
            - sentence_count: Number of sentences
            - avg_words_per_sentence: Average words per sentence
            - text_ratio: Non-HTML chars / total chars as percentage
            - readability: Flesch reading ease score
            - readability_grade: Text difficulty grade (e.g., "Hard", "Normal")
            - hash: MD5 hash for exact duplicate detection
            - text_content: Cleaned text for similarity analysis
        """
        soup = BeautifulSoup(html, 'lxml')

        # Extract body content
        body = soup.find('body')
        if not body:
            body = soup

        # Remove script, style, and nav/footer elements
        for tag in body.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # Get text content
        text_content = body.get_text()

        # Clean and normalize text
        text_content = re.sub(r'\s+', ' ', text_content).strip()

        # Calculate word count
        words = self._tokenize_words(text_content)
        word_count = len(words)

        # Calculate sentence count
        sentences = self._count_sentences(text_content)
        sentence_count = len(sentences)
        
        # Calculate average words per sentence
        avg_words_per_sentence = 0.0
        if sentence_count > 0:
            avg_words_per_sentence = round(word_count / sentence_count, 3)

        # Calculate text ratio
        total_chars = len(html)
        text_chars = len(text_content)
        text_ratio = (text_chars / total_chars * 100) if total_chars > 0 else 0

        # Calculate readability score
        readability = self._calculate_readability(text_content)
        
        # Get readability grade
        readability_grade = self._get_readability_grade(readability)

        # Calculate content hash
        content_hash = self._calculate_hash(text_content)

        result = {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'avg_words_per_sentence': avg_words_per_sentence,
            'text_ratio': round(text_ratio, 3),
            'readability': round(readability, 3),
            'readability_grade': readability_grade,
            'hash': content_hash,
            'text_content': text_content,  # Keep for similarity analysis
        }

        # Store hash for duplicate detection
        self.content_hashes[url] = content_hash

        return result
    
    def _count_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        Matches Screaming Frog's sentence counting methodology:
        - Each sentence-ending punctuation creates a break
        - Colons, semicolons also create breaks
        - Counts word groups of 2+ words as sentence units
        
        Screaming Frog seems to count on word boundaries more aggressively,
        resulting in higher sentence counts and lower avg words/sentence.
        """
        if not text:
            return []
        
        # Split on sentence-ending punctuation AND other common breaks
        # Screaming Frog appears to split more aggressively than traditional sentence detection
        # Include: periods, questions, exclamations, colons, semicolons, em-dashes, bullets
        sentences = re.split(r'[.!?;:•–—]+|\n+', text)
        
        # Filter to segments with at least 2 words (count each as a sentence unit)
        valid_sentences = []
        for s in sentences:
            s = s.strip()
            words = s.split()
            if len(words) >= 2:
                valid_sentences.append(s)
        
        return valid_sentences
    
    def _get_readability_grade(self, flesch_score: float) -> str:
        """
        Convert Flesch Reading Ease score to grade
        
        90-100: Very Easy
        80-89: Easy
        70-79: Fairly Easy
        60-69: Normal
        50-59: Fairly Hard
        30-49: Hard
        0-29: Very Hard
        """
        if flesch_score >= 90:
            return "Very Easy"
        elif flesch_score >= 80:
            return "Easy"
        elif flesch_score >= 70:
            return "Fairly Easy"
        elif flesch_score >= 60:
            return "Normal"
        elif flesch_score >= 50:
            return "Fairly Hard"
        elif flesch_score >= 30:
            return "Hard"
        else:
            return "Very Hard"

    def _tokenize_words(self, text: str) -> List[str]:
        """Tokenize text into words"""
        # Remove punctuation and split on whitespace
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
        return words

    def _calculate_readability(self, text: str) -> float:
        """
        Calculate Flesch Reading Ease score

        Score interpretation:
        - 90-100: Very Easy (5th grade)
        - 80-89: Easy (6th grade)
        - 70-79: Fairly Easy (7th grade)
        - 60-69: Standard (8th-9th grade)
        - 50-59: Fairly Difficult (10th-12th grade)
        - 30-49: Difficult (College)
        - 0-29: Very Confusing (College graduate)

        Formula: 206.835 - 1.015 * (total words / total sentences) - 84.6 * (total syllables / total words)
        """
        if not text:
            return 0.0

        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)

        if sentence_count == 0:
            return 0.0

        # Count words
        words = self._tokenize_words(text)
        word_count = len(words)

        if word_count == 0:
            return 0.0

        # Count syllables
        syllable_count = sum(self._count_syllables(word) for word in words)

        # Calculate Flesch Reading Ease
        avg_words_per_sentence = word_count / sentence_count
        avg_syllables_per_word = syllable_count / word_count

        score = 206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return round(score, 1)

    def _count_syllables(self, word: str) -> int:
        """
        Estimate syllable count in a word

        Simple algorithm:
        - Count vowel groups (consecutive vowels = 1 syllable)
        - Subtract silent 'e' at end
        - Minimum 1 syllable per word
        """
        word = word.lower()

        # Handle special cases
        if len(word) <= 3:
            return 1

        # Remove silent 'e' at end
        if word.endswith('e'):
            word = word[:-1]

        # Count vowel groups
        vowels = 'aeiouy'
        syllable_count = 0
        previous_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel

        # Minimum 1 syllable
        return max(1, syllable_count)

    def _calculate_hash(self, text: str) -> str:
        """Calculate MD5 hash of text content"""
        hash_obj = hashlib.md5(text.encode('utf-8'))
        return hash_obj.hexdigest()

    def find_exact_duplicates(self, urls_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Find exact duplicate content (same hash)

        Args:
            urls_data: Dict mapping URL -> {hash, ...}

        Returns:
            Dict mapping hash -> list of URLs with that hash
        """
        hash_to_urls = {}

        for url, data in urls_data.items():
            content_hash = data.get('hash')
            if content_hash:
                if content_hash not in hash_to_urls:
                    hash_to_urls[content_hash] = []
                hash_to_urls[content_hash].append(url)

        # Filter to only duplicates (more than 1 URL per hash)
        duplicates = {h: urls for h, urls in hash_to_urls.items() if len(urls) > 1}

        return duplicates

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts using Jaccard similarity on word n-grams

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Generate word trigrams
        ngrams1 = self._generate_ngrams(text1, n=3)
        ngrams2 = self._generate_ngrams(text2, n=3)

        if not ngrams1 or not ngrams2:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)

        similarity = intersection / union if union > 0 else 0.0

        return similarity

    def _generate_ngrams(self, text: str, n: int = 3) -> Set[str]:
        """Generate word n-grams from text"""
        words = self._tokenize_words(text.lower())

        if len(words) < n:
            return set()

        ngrams = set()
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i + n])
            ngrams.add(ngram)

        return ngrams

    def find_near_duplicates(
        self,
        urls_data: Dict[str, Dict[str, Any]],
        threshold: float = 0.9
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find near-duplicate content (90%+ similarity)

        Args:
            urls_data: Dict mapping URL -> {text_content, ...}
            threshold: Similarity threshold (default 0.9 = 90%)

        Returns:
            Dict mapping URL -> list of similar URLs with similarity scores
        """
        near_duplicates = {}

        urls = list(urls_data.keys())

        for i, url1 in enumerate(urls):
            text1 = urls_data[url1].get('text_content', '')
            if not text1:
                continue

            similar_pages = []

            for url2 in urls[i + 1:]:
                text2 = urls_data[url2].get('text_content', '')
                if not text2:
                    continue

                # Check cache
                cache_key = (url1, url2)
                if cache_key in self.content_similarity_cache:
                    similarity = self.content_similarity_cache[cache_key]
                else:
                    similarity = self.calculate_similarity(text1, text2)
                    self.content_similarity_cache[cache_key] = similarity

                if similarity >= threshold:
                    similar_pages.append({
                        'url': url2,
                        'similarity': round(similarity * 100, 2),
                    })

            if similar_pages:
                near_duplicates[url1] = similar_pages

        return near_duplicates

    def analyze_content_issues(self, data: Dict[str, Any]) -> List[str]:
        """
        Identify content issues

        Returns:
            List of issue codes
        """
        issues = []

        word_count = data.get('word_count', 0)
        text_ratio = data.get('text_ratio', 0)

        if word_count < 200:
            issues.append('low_content')

        if text_ratio < 10:
            issues.append('low_text_ratio')

        # Note: Spelling and grammar errors would require external libraries
        # like LanguageTool or Grammarly API

        return issues

    def extract_language_from_content(self, text: str) -> Optional[str]:
        """
        Detect language from content (basic implementation)

        For production, use libraries like langdetect or lingua

        Returns:
            ISO language code (e.g., 'en', 'es')
        """
        # Simple heuristic: check for common words
        common_words = {
            'en': ['the', 'and', 'is', 'in', 'to', 'of', 'a', 'for', 'on', 'with'],
            'es': ['el', 'la', 'de', 'que', 'y', 'en', 'un', 'ser', 'por', 'con'],
            'fr': ['le', 'de', 'un', 'être', 'et', 'à', 'il', 'avoir', 'ne', 'je'],
            'de': ['der', 'die', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit', 'sich'],
        }

        words = self._tokenize_words(text.lower())
        word_set = set(words[:100])  # Check first 100 words

        # Count matches for each language
        scores = {}
        for lang, common in common_words.items():
            score = sum(1 for word in common if word in word_set)
            scores[lang] = score

        # Return language with highest score
        if scores:
            best_lang = max(scores, key=scores.get)
            if scores[best_lang] > 0:
                return best_lang

        return None

    def calculate_keyword_density(self, text: str, keyword: str) -> float:
        """
        Calculate keyword density

        Args:
            text: Page text content
            keyword: Keyword or phrase to search for

        Returns:
            Keyword density as percentage
        """
        words = self._tokenize_words(text.lower())
        keyword_lower = keyword.lower()

        # Count occurrences
        keyword_words = self._tokenize_words(keyword_lower)
        keyword_count = 0

        if len(keyword_words) == 1:
            # Single word
            keyword_count = words.count(keyword_words[0])
        else:
            # Multi-word phrase
            for i in range(len(words) - len(keyword_words) + 1):
                phrase = ' '.join(words[i:i + len(keyword_words)])
                if phrase == ' '.join(keyword_words):
                    keyword_count += 1

        total_words = len(words)
        density = (keyword_count / total_words * 100) if total_words > 0 else 0

        return round(density, 2)

    def extract_top_keywords(self, text: str, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        Extract top keywords by frequency (excluding common stop words)

        Args:
            text: Page text content
            top_n: Number of top keywords to return

        Returns:
            List of dicts with keyword and frequency
        """
        # Common English stop words
        stop_words = {
            'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
            'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
            'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
            'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their',
            'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go',
            'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
            'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them',
            'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over',
            'think', 'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work',
            'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
            'give', 'day', 'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had',
        }

        words = self._tokenize_words(text.lower())

        # Count word frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        # Return top N
        top_keywords = [
            {'keyword': word, 'frequency': freq}
            for word, freq in sorted_words[:top_n]
        ]

        return top_keywords

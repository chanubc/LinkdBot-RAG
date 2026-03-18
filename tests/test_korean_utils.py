"""Tests for Korean language utilities - particle stripping."""

from app.infrastructure.rag.korean_utils import (
    strip_particles,
    normalize_korean_query,
)


class TestStripParticles:
    """Tests for strip_particles function."""

    def test_strip_particles_basic(self):
        """Basic particle stripping: '채용공고를' → '채용공고'"""
        assert strip_particles("채용공고를") == "채용공고"

    def test_strip_particles_multiple_particles(self):
        """Multiple particle types: '증권에서' → '증권'"""
        assert strip_particles("증권에서") == "증권"

    def test_strip_particles_preserve_short_token(self):
        """Preserve single character tokens after strip is too short: '을' → '을'"""
        assert strip_particles("을") == "을"

    def test_strip_particles_non_korean_unchanged(self):
        """Non-Korean tokens unchanged: 'AI' → 'AI'"""
        assert strip_particles("AI") == "AI"

    def test_strip_particles_mixed_korean_english(self):
        """Mixed Korean/English: 'AI개발자를' → 'AI개발자'"""
        assert strip_particles("AI개발자를") == "AI개발자"

    def test_strip_particles_no_particle(self):
        """Token without particles unchanged: '채용공고' → '채용공고'"""
        assert strip_particles("채용공고") == "채용공고"

    def test_strip_particles_ga_subject_marker(self):
        """Subject marker particle: '일이' → '일이' (too short after strip, keep original)"""
        assert strip_particles("일이") == "일이"

    def test_strip_particles_wa_and_particle(self):
        """'와' and particle: '개발과' → '개발'"""
        assert strip_particles("개발과") == "개발"

    def test_strip_particles_eun_topic_marker(self):
        """Topic marker: '검색은' → '검색'"""
        assert strip_particles("검색은") == "검색"

    def test_strip_particles_neun_topic_marker(self):
        """Alternative topic marker: '엔지니어는' → '엔지니어'"""
        assert strip_particles("엔지니어는") == "엔지니어"


class TestNormalizeKoreanQuery:
    """Tests for normalize_korean_query function."""

    def test_normalize_korean_query_with_particles(self):
        """Normalize query with particles: '채용공고를 찾습니다' → tokens without particles"""
        result = normalize_korean_query("채용공고를 찾습니다")
        assert isinstance(result, list)
        assert "채용공고" in result
        assert len(result) >= 2

    def test_normalize_korean_query_simple(self):
        """Simple normalized query: '하나 증권' → ['하나', '증권']"""
        result = normalize_korean_query("하나 증권")
        assert isinstance(result, list)
        assert "하나" in result or any("하나" in t for t in result)
        assert "증권" in result

    def test_normalize_korean_query_with_multiple_particles(self):
        """Multiple particles: '채용공고를 찾습니다' should handle all"""
        result = normalize_korean_query("채용공고를 찾습니다")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_normalize_korean_query_empty_string(self):
        """Empty query normalization"""
        result = normalize_korean_query("")
        assert isinstance(result, list)
        assert result == [] or all(t for t in result)

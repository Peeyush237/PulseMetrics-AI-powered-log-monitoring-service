from app.services.clustering import ClusteringService


class TestNormalize:
    def test_uuids_replaced(self):
        msg = "Request abc123ef-1234-1234-1234-abcdef012345 failed"
        result = ClusteringService._normalize(msg)
        assert "<UUID>" in result
        assert "abc123ef" not in result

    def test_numbers_replaced(self):
        result = ClusteringService._normalize("Timeout after 3.2 seconds")
        assert "<NUM>" in result
        assert "3.2" not in result

    def test_timestamps_replaced(self):
        result = ClusteringService._normalize("Error at 2026-01-15T10:30:00Z in processing")
        assert "<TIMESTAMP>" in result

    def test_lowercased(self):
        result = ClusteringService._normalize("Connection FAILED")
        assert result == result.lower()

    def test_similar_messages_normalize_to_same(self):
        msg1 = "Connection to host db-1 failed after 3.2s"
        msg2 = "Connection to host db-7 failed after 5.8s"
        n1 = ClusteringService._normalize(msg1)
        n2 = ClusteringService._normalize(msg2)
        assert n1 == n2

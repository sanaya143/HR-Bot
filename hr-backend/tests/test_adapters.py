import unittest
from types import SimpleNamespace as NS

from hr_assistant.embeddings import sigmoid
from hr_assistant.models import Chunk
from hr_assistant.vector_store import (batches, build_filter, check_schema, chunk_from_match,
                                       field_value, to_document)


def make_chunk(page=None):
    meta = {"policy_category": "Leave", "country": ["IN"], "employment_type": ["ALL"],
            "role_level": ["ALL"], "status": "active", "effective_date": "", "version": "1",
            "title": "Leave"}
    return Chunk("id1", "12 days of leave", "leave.txt", "Leave", page, meta)


class Adapters(unittest.TestCase):
    def test_sigmoid(self):
        self.assertAlmostEqual(sigmoid(0), 0.5)
        self.assertGreater(sigmoid(5), 0.99)
        self.assertLess(sigmoid(-5), 0.01)
        self.assertGreaterEqual(sigmoid(-800), 0.0)
        self.assertLessEqual(sigmoid(800), 1.0)

    def test_filter_is_and_of_in_clauses(self):
        f = build_filter({"country": ["IN", "ALL"], "status": ["active"]})
        self.assertEqual(f, {"$and": [{"country": {"$in": ["IN", "ALL"]}},
                                      {"status": {"$in": ["active"]}}]})

    def test_document_shape(self):
        doc = to_document(make_chunk(), [0.1, 0.2])
        self.assertEqual(doc["_id"], "id1")
        self.assertEqual(doc["embedding"], [0.1, 0.2])
        self.assertEqual(doc["country"], ["IN"])
        self.assertNotIn("page", doc)
        self.assertTrue(all(v is not None for v in doc.values()))
        self.assertEqual(to_document(make_chunk(page=4), [0.1])["page"], 4)

    def test_match_parsing_handles_sdk_variants(self):
        doc = to_document(make_chunk(page=3), [0.1])
        obj_old = NS(_id="id1", _score=0.7, **{k: v for k, v in doc.items() if k not in ("_id", "embedding")})
        obj_new = NS(id="id1", score=0.7, **{k: v for k, v in doc.items() if k not in ("_id", "embedding")})
        as_dict = {**doc, "_score": 0.7}
        for m in (obj_old, obj_new, as_dict):
            c = chunk_from_match(m)
            self.assertEqual((c.id, c.text, c.source, c.page), ("id1", "12 days of leave", "leave.txt", 3))
            self.assertAlmostEqual(c.score, 0.7)
            self.assertEqual(c.metadata["country"], ["IN"])

    def test_fields_inside_a_container(self):
        m = NS(id="x", score=0.5, fields={"text": "hello", "source": "a.txt"})
        c = chunk_from_match(m)
        self.assertEqual((c.text, c.source, c.page), ("hello", "a.txt", None))
        self.assertIsNone(field_value(m, "missing"))

    def test_schema_check(self):
        good = NS(schema=NS(fields={"embedding": {"dimension": 384}}))
        check_schema(good, 384)
        with self.assertRaises(RuntimeError):
            check_schema(NS(schema=NS(fields={"other": {}})), 384)
        with self.assertRaises(RuntimeError):
            check_schema(good, 768)
        check_schema(NS(), 384)          # cannot introspect -> no error

    def test_batches(self):
        self.assertEqual([len(b) for b in batches(list(range(250)), 100)], [100, 100, 50])


if __name__ == "__main__":
    unittest.main()

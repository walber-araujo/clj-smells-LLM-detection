from .base import VectorDBClient, ContextPackage, CodeExample


# ---------------------------------------------------------------------------
# Hardcoded evidence for PoC. Replace each entry with real vector DB results
# when a provider is wired in.
# ---------------------------------------------------------------------------

_MOCK_DATA: dict[str, list[dict]] = {
    "unmanaged_resource_io": [
        {
            "label": "positive",
            "source": "README catalog example",
            "description": "Reader opened without with-open — will leak the resource.",
            "code": """\
(defn read-file-smelly [filename]
  (let [reader (io/reader filename)]
    (line-seq reader)))""",
        },
        {
            "label": "negative",
            "source": "Clojure docs — with-open idiom",
            "description": "with-open guarantees the reader is closed even if an exception occurs.",
            "code": """\
(defn read-file-clean [filename]
  (with-open [reader (io/reader filename)]
    (doall (line-seq reader))))""",
        },
        {
            "label": "refactoring",
            "source": "Community blog: Clojure resource management",
            "description": "Wrap the binding with with-open and force realisation with doall inside.",
            "code": """\
;; BEFORE (smelly)
(let [reader (io/reader filename)]
  (line-seq reader))

;; AFTER (clean)
(with-open [reader (io/reader filename)]
  (doall (line-seq reader)))""",
        },
        {
            "label": "survey_comment",
            "source": "Survey respondent #12",
            "description": None,
            "code": "\"Always use with-open for anything that implements Closeable. "
                    "Forgetting it in production causes subtle connection-pool exhaustion.\"",
        },
    ],

    "blocking_inside_go": [
        {
            "label": "positive",
            "source": "README catalog example",
            "description": "alts!! is a double-bang (blocking) op used inside a go block.",
            "code": """\
(a/go
  (a/alts!! [started-chan (a/timeout 1000)])
  (a/close! result-chan))""",
        },
        {
            "label": "negative",
            "source": "Clojure core.async guide",
            "description": "Use single-bang variants inside go blocks — they park, not block.",
            "code": """\
(a/go
  (a/alts! [started-chan (a/timeout 1000)])
  (a/close! result-chan))""",
        },
        {
            "label": "refactoring",
            "source": "core.async best practices",
            "description": "Replace blocking ops (!! suffix) with parking ops (! suffix) inside go.",
            "code": """\
;; BEFORE: blocks the thread pool
(a/go (a/<!! some-chan))

;; AFTER: parks the go block correctly
(a/go (a/<! some-chan))""",
        },
    ],

    "unnecessary_laziness": [
        {
            "label": "positive",
            "source": "README catalog example",
            "description": "map returns a lazy seq, then vec forces it — double pass for no reason.",
            "code": """\
(defn process-smelly [coll]
  (let [doubled (map #(* 2 %) coll)]
    (vec doubled)))""",
        },
        {
            "label": "negative",
            "source": "Clojure style guide",
            "description": "mapv is eager and communicates intent clearly.",
            "code": """\
(defn process-clean [coll]
  (mapv #(* 2 %) coll))""",
        },
        {
            "label": "refactoring",
            "source": "Community review",
            "description": "Replace map+vec with mapv; replace filter+vec with filterv.",
            "code": """\
;; BEFORE
(vec (map f coll))
(vec (filter pred coll))

;; AFTER
(mapv f coll)
(filterv pred coll)""",
        },
    ],

    "improper_emptiness_check": [
        {
            "label": "positive",
            "source": "README catalog example",
            "description": "not+empty? is more verbose and less idiomatic than seq.",
            "code": """\
(when (not (empty? x)) ...)
(when-not (empty? x) ...)""",
        },
        {
            "label": "negative",
            "source": "Clojure style guide — emptiness",
            "description": "seq returns nil for empty/nil and a truthy seq otherwise.",
            "code": """\
(when (seq x) ...)""",
        },
    ],

    "nested_atoms": [
        {
            "label": "positive",
            "source": "README catalog example",
            "description": "Atom inside an atom breaks atomic snapshots of the full state.",
            "code": """\
(def global-state
  (atom {:ui-state  {:theme :light}
         :history   (atom [])}))""",
        },
        {
            "label": "negative",
            "source": "Clojure concurrency patterns",
            "description": "Keep all state in a single atom with a nested plain map.",
            "code": """\
(def global-state
  (atom {:ui-state {:theme :light}
         :history  []}))""",
        },
        {
            "label": "refactoring",
            "source": "State management guide",
            "description": "Flatten the nested atom into the parent atom's value.",
            "code": """\
;; BEFORE
(def state (atom {:data (atom [])}))
(swap! (:data @state) conj item)   ; only inner atom changes

;; AFTER
(def state (atom {:data []}))
(swap! state update :data conj item)  ; whole state updated atomically""",
        },
    ],
}

import re
from pathlib import Path

def _parse_dataset_example(md_path: Path) -> dict:
    content = md_path.read_text(encoding="utf-8")
    
    desc_match = re.search(r"\*\s+\*\*Short explanation:\*\*\s+(.*)", content)
    description = desc_match.group(1).strip() if desc_match else None
    
    code_match = re.search(r"```[cC]lojure\n(.*?)\n```", content, re.DOTALL)
    code = code_match.group(1).strip() if code_match else ""
    
    label = "positive"
    name_lower = md_path.name.lower()
    if "good" in name_lower:
        label = "negative"
    elif "refactor" in name_lower:
        label = "refactoring"
        
    return {
        "label": label,
        "source": f"Dataset: {md_path.name}",
        "description": description,
        "code": code
    }

class MockVectorDBClient(VectorDBClient):
    """
    Hardcoded vector DB for PoC.
    Returns examples dynamically loaded from the clj-smells-dataset.
    Falls back to pre-written examples if not found in the dataset.
    """

    def query(self, smell_id: str, snippet: str, top_k: int = 3) -> ContextPackage:
        pkg = ContextPackage(smell_id=smell_id)
        
        dataset_path = Path("/Users/walber.filho.nufuturo/clj-smells-dataset/smells")
        smell_dirs = list(dataset_path.rglob(smell_id))
        
        raw_docs = []
        if smell_dirs and smell_dirs[0].is_dir():
            for md_file in smell_dirs[0].glob("*.md"):
                try:
                    raw_docs.append(_parse_dataset_example(md_file))
                except Exception:
                    pass
                    
        # Fallback to hardcoded mock data if dataset doesn't have it
        if not raw_docs:
            raw_docs = _MOCK_DATA.get(smell_id, [])

        for doc in raw_docs[:top_k * 5]:   # no real ranking — just group by label
            example = CodeExample(
                code=doc["code"],
                label=doc["label"],
                source=doc["source"],
                description=doc.get("description"),
            )
            label_key = "survey_comments" if doc["label"] == "survey_comment" else doc["label"]
            if label_key not in pkg.examples:
                label_key = "docs"
            pkg.examples[label_key].append(example)

        return pkg

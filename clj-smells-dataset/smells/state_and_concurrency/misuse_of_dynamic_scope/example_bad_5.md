## Metadata

* **Smell name:** misuse_of_dynamic_scope
* **Expected smell location:** Top-level def `*current-document*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Using dynamic scope for ordinary application data like a document makes data flow implicit and harder to reason about.

```Clojure
(ns app.editor.document)

; VALIDATION: SMELL START - misuse_of_dynamic_scope
; VALIDATION: Using dynamic scope for ordinary application data (current document)
(def ^:dynamic *current-document* nil)
; VALIDATION: SMELL END

(defn word-count
  []
  (count (clojure.string/split (:text *current-document*) #"\s+")))

(defn analyze-document
  [doc]
  (binding [*current-document* doc]
    {:words (word-count)}))
```

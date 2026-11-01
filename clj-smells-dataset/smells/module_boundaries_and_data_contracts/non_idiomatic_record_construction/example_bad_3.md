## Metadata

* **Smell name:** non_idiomatic_record_construction
* **Expected smell location:** Function body
* **Affected forms:** `RecordName.`
* **Short explanation:** Using Java interop syntax `(RecordName. args...)` to construct records is less idiomatic than using the auto-generated factory functions like `->RecordName` or `map->RecordName`.

```Clojure
(ns app.auth)

(defrecord Token [value expires-at])

(defn generate-token []
; VALIDATION: SMELL START - non_idiomatic_record_construction
; VALIDATION: Java interop syntax for record creation
  (Token. "abc123xyz" 1700000000))
; VALIDATION: SMELL END
```

## Metadata

* **Smell name:** non_idiomatic_record_construction
* **Expected smell location:** Function body
* **Affected forms:** `RecordName.`
* **Short explanation:** Using Java interop syntax `(RecordName. args...)` to construct records is less idiomatic than using the auto-generated factory functions like `->RecordName` or `map->RecordName`.

```Clojure
(ns app.models)

(defrecord User [id name])

(defn make-user [id name]
; VALIDATION: SMELL START - non_idiomatic_record_construction
; VALIDATION: using Java interop constructor syntax for records
  (User. id name))
; VALIDATION: SMELL END
```

## Metadata

* **Smell name:** non_idiomatic_record_construction
* **Expected smell location:** Function body
* **Affected forms:** `RecordName.`
* **Short explanation:** Using factory functions like `->RecordName` or `map->RecordName` is more idiomatic and allows records to be used seamlessly as functions.

```Clojure
(ns app.config)

(defrecord Config [host port])

(defn default-config []
  (map->Config {:host "localhost" :port 8080}))
```

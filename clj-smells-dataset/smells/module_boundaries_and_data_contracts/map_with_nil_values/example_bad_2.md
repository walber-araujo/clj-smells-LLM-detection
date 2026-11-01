## Metadata

* **Smell name:** map_with_nil_values
* **Expected smell location:** Map literal or `assoc`
* **Affected forms:** `{}`, `assoc`
* **Short explanation:** Explicitly putting `nil` values into maps is unidiomatic in Clojure. In Clojure, an absent key is treated as `nil`, so it is better to omit the key entirely rather than including it with a `nil` value.

```Clojure
(ns app.config)

(defn get-config []
; VALIDATION: SMELL START - map_with_nil_values
; VALIDATION: explicit nil value in map literal
  {:host "localhost"
   :port 8080
   :password nil})
; VALIDATION: SMELL END
```

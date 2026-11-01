## Metadata

* **Smell name:** map_with_nil_values
* **Expected smell location:** Map literal or `assoc`
* **Affected forms:** `{}`, `assoc`
* **Short explanation:** Explicitly putting `nil` values into maps is unidiomatic in Clojure. In Clojure, an absent key is treated as `nil`, so it is better to omit the key entirely rather than including it with a `nil` value.

```Clojure
(ns app.profile)

(defn build-profile [name age email]
; VALIDATION: SMELL START - map_with_nil_values
; VALIDATION: explicitly associng potentially nil values into a map
  {:name name
   :age age
   :email nil})
; VALIDATION: SMELL END
```

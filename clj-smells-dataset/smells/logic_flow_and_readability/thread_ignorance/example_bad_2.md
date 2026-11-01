## Metadata

* **Smell name:** thread_ignorance
* **Expected smell location:** Function `format-output`
* **Affected forms:** `let`
* **Short explanation:** Binds intermediate variables in a let block for a series of string transformations that would be cleaner with ->.

```Clojure
(ns text.formatter
  (:require [clojure.string :as str]))

(defn format-output [raw-text]
  ; VALIDATION: SMELL START - thread_ignorance
  ; VALIDATION: Sequential transformations in let bindings rather than using ->
  (let [trimmed (str/trim raw-text)
        lowercased (str/lower-case trimmed)
        replaced (str/replace lowercased #"\s+" "-")]
    replaced))
  ; VALIDATION: SMELL END
```

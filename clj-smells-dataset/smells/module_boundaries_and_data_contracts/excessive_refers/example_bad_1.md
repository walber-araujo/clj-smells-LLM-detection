## Metadata

* **Smell name:** excessive_refers
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:refer`
* **Short explanation:** Using `:refer` with a very long list of symbols clutters the namespace declaration and makes it hard to maintain. It also pollutes the current namespace.

```Clojure
(ns app.core
; VALIDATION: SMELL START - excessive_refers
; VALIDATION: excessively long list of referred symbols
  (:require [clojure.string :refer [join split upper-case lower-case trim replace capitalize blank? includes? starts-with? ends-with? index-of]]
            [app.utils :refer [a b c d e f g h i j k]]))
; VALIDATION: SMELL END

(defn process [s]
  (if (blank? s)
    ""
    (upper-case (trim s))))
```

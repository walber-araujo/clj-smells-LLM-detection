## Metadata

* **Smell name:** thread_ignorance
* **Expected smell location:** Function `format-output`
* **Affected forms:** `->`
* **Short explanation:** Refactored to use the -> threading macro for string transformation steps.

```Clojure
(ns text.formatter
  (:require [clojure.string :as str]))

(defn format-output [raw-text]
  (-> raw-text
      str/trim
      str/lower-case
      (str/replace #"\s+" "-")))
```

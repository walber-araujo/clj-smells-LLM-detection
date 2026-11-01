## Metadata

* **Smell name:** Namespace Load Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `require`, `requiring-resolve`
* **Short explanation:** Dependencies should be explicitly declared within the `ns` form using `:require`.

```Clojure
(ns reporting.core
  (:require [clojure.string :as str]))

(defn generate-report [data]
  (str/join "," data))
```

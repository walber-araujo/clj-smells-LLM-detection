## Metadata

* **Smell name:** excessive_refers
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:refer`
* **Short explanation:** Using `:as` to create a namespace alias is cleaner, prevents naming collisions, and makes it clear where functions originate.

```Clojure
(ns app.core
  (:require [clojure.string :as str]
            [app.utils :as u]))

(defn process [s]
  (if (str/blank? s)
    ""
    (str/upper-case (str/trim s))))
```

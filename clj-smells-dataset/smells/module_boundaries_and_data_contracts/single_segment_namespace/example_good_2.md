## Metadata

* **Smell name:** single_segment_namespace
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`
* **Short explanation:** Using multi-segment namespaces (often prefixed with a project or organization name) prevents naming collisions.

```Clojure
(ns myapp.config
  (:require [clojure.edn :as edn]))

(defn load-config []
  (edn/read-string (slurp "config.edn")))
```

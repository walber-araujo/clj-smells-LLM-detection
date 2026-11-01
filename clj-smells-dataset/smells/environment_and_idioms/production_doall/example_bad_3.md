## Metadata

* **Smell name:** Production doall
* **Expected smell location:** Function `notify-users`, `save-records`
* **Affected forms:** `doall`
* **Short explanation:** Using `doall` with `map` just to force side effects is non-idiomatic and creates an unnecessary intermediate sequence in memory.

```Clojure
(ns app.sync
  (:require [clj-http.client :as http]))

(defn sync-files [urls]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall to force http calls
  (doall (map #(http/post %) urls)))
  ; VALIDATION: SMELL END
```

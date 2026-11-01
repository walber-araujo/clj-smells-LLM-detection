## Metadata

* **Smell name:** Relying on Load-Time Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `def`
* **Short explanation:** Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.

```Clojure
(ns app.file-cache
  (:require [clojure.edn :as edn]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Reading a file into memory at load time
(def cached-data
  (edn/read-string (slurp "data/cache.edn")))
; VALIDATION: SMELL END
```

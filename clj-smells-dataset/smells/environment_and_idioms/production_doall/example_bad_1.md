## Metadata

* **Smell name:** Production doall
* **Expected smell location:** Function `notify-users`, `save-records`
* **Affected forms:** `doall`
* **Short explanation:** Using `doall` with `map` just to force side effects is non-idiomatic and creates an unnecessary intermediate sequence in memory.

```Clojure
(ns app.notifications
  (:require [app.email :as email]))

(defn notify-users [users]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall used purely for side-effects instead of run! or doseq
  (doall (map email/send-welcome! users)))
  ; VALIDATION: SMELL END
```

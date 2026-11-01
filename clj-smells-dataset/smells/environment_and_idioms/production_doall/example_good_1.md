## Metadata

* **Smell name:** Production doall
* **Expected smell location:** Function `notify-users`, `save-records`
* **Affected forms:** `doall`
* **Short explanation:** Use `run!` or `doseq` to perform side effects over a sequence without retaining the results.

```Clojure
(ns app.notifications
  (:require [app.email :as email]))

(defn notify-users [users]
  (run! email/send-welcome! users))
```

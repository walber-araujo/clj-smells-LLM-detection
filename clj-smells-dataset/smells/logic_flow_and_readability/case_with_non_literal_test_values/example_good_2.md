## Metadata

* **Smell name:** case_with_non_literal_test_values
* **Expected smell location:** Function `route-message`
* **Affected forms:** `cond`
* **Short explanation:** Refactored to use cond, correctly comparing the dynamic variables.

```Clojure
(ns msg.router)

(defn route-message [msg]
  (let [admin-topic "topic.admin"
        user-topic  "topic.user"
        topic       (:topic msg)]
    (cond
      (= topic admin-topic) (handle-admin msg)
      (= topic user-topic)  (handle-user msg)
      :else                 (drop-message msg))))
```

## Metadata

* **Smell name:** case_with_non_literal_test_values
* **Expected smell location:** Function `route-message`
* **Affected forms:** `case`
* **Short explanation:** Attempts to use a let binding as a case branch test value, which is invalid logic in Clojure.

```Clojure
(ns msg.router)

(defn route-message [msg]
  (let [admin-topic "topic.admin"
        user-topic  "topic.user"]
    ; VALIDATION: SMELL START - case_with_non_literal_test_values
    ; VALIDATION: case uses admin-topic and user-topic as symbols, not their bound string values
    (case (:topic msg)
      admin-topic (handle-admin msg)
      user-topic  (handle-user msg)
      (drop-message msg))))
  ; VALIDATION: SMELL END
```

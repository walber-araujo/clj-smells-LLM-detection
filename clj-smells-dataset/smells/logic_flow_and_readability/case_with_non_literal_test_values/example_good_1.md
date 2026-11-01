## Metadata

* **Smell name:** case_with_non_literal_test_values
* **Expected smell location:** Function `handle-event`
* **Affected forms:** `condp`
* **Short explanation:** Refactored to use condp, which correctly evaluates the branch test values.

```Clojure
(ns event.handler)

(def click-event :ui/click)
(def hover-event :ui/hover)

(defn handle-event [event-type data]
  (condp = event-type
    click-event (process-click data)
    hover-event (process-hover data)
    (log/warn "Unknown event")))
```

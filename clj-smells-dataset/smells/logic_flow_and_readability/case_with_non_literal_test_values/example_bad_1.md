## Metadata

* **Smell name:** case_with_non_literal_test_values
* **Expected smell location:** Function `handle-event`
* **Affected forms:** `case`
* **Short explanation:** Uses `case` with variables (which evaluates them as unquoted symbols/literals) instead of `cond` or `condp`.

```Clojure
(ns event.handler)

(def click-event :ui/click)
(def hover-event :ui/hover)

(defn handle-event [event-type data]
  ; VALIDATION: SMELL START - case_with_non_literal_test_values
  ; VALIDATION: Using case with defs/vars as test values; case treats them as literals
  (case event-type
    click-event (process-click data)
    hover-event (process-hover data)
    (log/warn "Unknown event")))
  ; VALIDATION: SMELL END
```

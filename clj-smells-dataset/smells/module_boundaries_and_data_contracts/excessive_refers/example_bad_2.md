## Metadata

* **Smell name:** excessive_refers
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:refer`
* **Short explanation:** Using `:refer` with a very long list of symbols clutters the namespace declaration and makes it hard to maintain. It also pollutes the current namespace.

```Clojure
(ns app.handler
; VALIDATION: SMELL START - excessive_refers
; VALIDATION: excessively long list of referred symbols
  (:require [ring.util.response :refer [response redirect not-found status header content-type charset set-cookie get-header bad-request created]]))
; VALIDATION: SMELL END

(defn ok-response [body]
  (-> (response body)
      (content-type "application/json")))
```

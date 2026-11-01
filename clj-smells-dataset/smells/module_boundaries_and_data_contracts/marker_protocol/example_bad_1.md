## Metadata

* **Smell name:** marker_protocol
* **Expected smell location:** Top-level form
* **Affected forms:** `defprotocol`
* **Short explanation:** Defining a protocol with no methods just to use it as a type marker via `satisfies?` is unidiomatic. In Clojure, metadata or sets are usually better suited for attaching markers to data.

```Clojure
(ns myapp.domain.entities)

; VALIDATION: SMELL START - marker_protocol
; VALIDATION: defining a protocol without methods to act as a marker type
(defprotocol Entity)
; VALIDATION: SMELL END

(defrecord User [id name]
  Entity)
```

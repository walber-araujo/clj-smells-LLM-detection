## Metadata

* **Smell name:** private_multimethods
* **Expected smell location:** Top-level form
* **Affected forms:** `defmulti`, `^:private`
* **Short explanation:** Defining a multimethod as private defeats its purpose. Multimethods are designed for open extension, and making them private prevents other namespaces from adding methods to them.

```Clojure
(ns myapp.transformation)

; VALIDATION: SMELL START - private_multimethods
; VALIDATION: private multimethod
(defmulti ^:private transform-payload :version)
; VALIDATION: SMELL END

(defmethod transform-payload "v1" [payload]
  (:data payload))
```

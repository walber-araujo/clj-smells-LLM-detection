## Metadata

* **Smell name:** private_multimethods
* **Expected smell location:** Top-level form
* **Affected forms:** `defmulti`, `^:private`
* **Short explanation:** Defining a multimethod as private defeats its purpose. Multimethods are designed for open extension, and making them private prevents other namespaces from adding methods to them.

```Clojure
(ns myapp.formatting)

; VALIDATION: SMELL START - private_multimethods
; VALIDATION: private multimethod
(defmulti ^:private format-value class)
; VALIDATION: SMELL END

(defmethod format-value String [s] s)
```

## Metadata

* **Smell name:** private_multimethods
* **Expected smell location:** Top-level form
* **Affected forms:** `defmulti`, `^:private`
* **Short explanation:** Defining a multimethod as private defeats its purpose. Multimethods are designed for open extension, and making them private prevents other namespaces from adding methods to them.

```Clojure
(ns myapp.dispatch)

; VALIDATION: SMELL START - private_multimethods
; VALIDATION: multimethod is private, restricting its extensibility
(defmulti ^:private dispatch-event :type)
; VALIDATION: SMELL END

(defmethod dispatch-event :user-created [_]
  (println "User created"))
```

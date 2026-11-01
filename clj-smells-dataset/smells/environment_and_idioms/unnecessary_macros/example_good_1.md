## Metadata

* **Smell name:** Unnecessary Macros
* **Expected smell location:** Macro `log-info`, `validate`
* **Affected forms:** `defmacro`
* **Short explanation:** Use a function instead of a macro when you don't need to control evaluation order or manipulate syntax.

```Clojure
(ns logging.core)

(defn log-info [msg]
  (println "[INFO]" msg))

(defn process []
  (log-info "Starting process"))
```

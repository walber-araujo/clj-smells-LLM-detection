## Metadata

* **Smell name:** Multiple Evaluation in Macros
* **Expected smell location:** Macro `unless`, `time-it`
* **Affected forms:** `defmacro`
* **Short explanation:** Macros should evaluate their arguments once by binding them to a gensym in a `let` block.

```Clojure
(ns utils.control
  (:require [clojure.tools.logging :as log]))

(defmacro unless [pred a b]
  `(let [p# ~pred]
     (if (not p#)
       (do
         (log/info "Pred was false:" '~pred)
         ~b)
       ~a)))
```

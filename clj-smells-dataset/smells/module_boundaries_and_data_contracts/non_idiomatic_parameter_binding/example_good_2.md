## Metadata

* **Smell name:** non_idiomatic_parameter_binding
* **Expected smell location:** Function parameter list
* **Affected forms:** `defn`
* **Short explanation:** Explicit multi-arity functions make the supported signatures clear and execute faster.

```Clojure
(ns app.users)

(defn create-user
  ([username] (create-user username "guest"))
  ([username role]
   {:username username :role role}))
```

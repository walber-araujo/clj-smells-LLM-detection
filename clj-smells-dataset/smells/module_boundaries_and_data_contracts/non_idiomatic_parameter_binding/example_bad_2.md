## Metadata

* **Smell name:** non_idiomatic_parameter_binding
* **Expected smell location:** Function parameter list
* **Affected forms:** `defn`
* **Short explanation:** Using variadic arguments (`& [opt]`) to destructure optional positional parameters is less clear and less idiomatic than using explicit multi-arity functions.

```Clojure
(ns app.users)

; VALIDATION: SMELL START - non_idiomatic_parameter_binding
; VALIDATION: using variadic args to simulate optional parameters
(defn create-user [username & [role]]
  {:username username :role (or role "guest")})
; VALIDATION: SMELL END
```

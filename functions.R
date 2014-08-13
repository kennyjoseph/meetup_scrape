get_cross_val_lists <- function(X,n){ 
  xval_set <- 1:n
  spl <- split(X,sample(xval_set,nrow(X),replace=TRUE))
  return(
    apply(combn(xval_set,n-1),2,
          function(f){
            return(
              list("test"=spl[[setdiff(xval_set,f)]], 
                   "train"=data.frame(rbindlist(spl[f])))
            )
          }
    )
  )
}

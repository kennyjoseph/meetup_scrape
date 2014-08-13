


d <- read.csv("~/Dropbox/Kenny/current_papers/current/meetup/group_shared_members.csv",sep="\t")
d$log_jac <- ifelse(d$jaccard != 0, log(d$jaccard), 0)
d$log_topic <- ifelse(d$topic_tfidf!= 0, log(d$topic_tfidf), 0)
d$log_shared <- ifelse(d$shared!= 0, log(d$shared), 0)
d$loc_sim <- 1-d$loc_sim
d$shared_bin <- cut(d$log_shared,8)
d$shared_any <- factor(ifelse(d$shared > 0,"t","f"))
d$description_sim[is.na(d$description_sim)] <- 0


predictors <- c("same_topic","loc_sim","description_sim","n_g1","n_g2","name_sim")
d_pred <- d[,c(predictors,"shared_any","g1_name","g2_name","shared", "g1_id","g2_id")]
d_pred[,predictors] <- scale(d_pred[,predictors],center=T, scale=2*as.vector(apply(d_pred[,predictors],2,sd)))
cv_dat <- get_cross_val_lists(d_pred,5)
train <- cv_dat[[1]][["train"]]

form <- formula(paste("shared_any",paste(paste(predictors,collapse="+"),"n_g1*n_g2","loc_sim*same_topic",sep="+"),sep="~"))
#form <- formula("shared_any~same_topic+description_sim+n_g1*n_g2")

mod <- glm(form, family=binomial,data=train)
train.rose <- ROSE(shared_any ~ same_topic+loc_sim+description_sim+n_g1+n_g2+name_sim,data=train,seed=123)$data
mod.rose <- glm(form, family=binomial,data=train.rose)

test <- cv_dat[[1]][["test"]]
test$pred_rose <- predict(mod.rose,newdata=test,type="response")
test$pred_reg <- predict(mod,newdata=test,type="response")

test$v_rose <- ifelse(test$pred_rose >=.5,"t","f")
test$v_reg <- ifelse(test$pred_reg >=.5,"t","f")

roc.curve(test$shared_any, test$pred_rose)
roc.curve(test$shared_any, test$pred_reg, add.roc=TRUE, col=2)
roc.curve(test$shared_any, rep(0,nrow(test)), add.roc=TRUE, col=3)

wrong <- test[test$shared_any != test$v_reg,]
(t[1,1]+t[2,2])/sum(t)


model  <- svm(form, data = d_pred)

x <- has_shared[,predictors]
y <- has_shared$shared
x$description_sim[is.na(x$description_sim)] <- 0

pac.knn<- knn.reg(x, y=y, k=2);
ggplot(data.frame(true=y,pred=pac.knn$pred), aes(true,pred)) + geom_point() + scale_x_log10() + scale_y_log10() + geom_abline(slope=1,color='red')


ggplot(d, aes(shared > 0, topic_tfidf)) + stat_summary(fun.data="mean_cl_boot")
ggplot(d, aes(shared > 0, description_sim)) + stat_summary(fun.data="mean_cl_boot")
ggplot(d, aes(shared > 0, abs(g1_create_time-g2_create_time))) + stat_summary(fun.data="mean_cl_boot")
ggplot(d, aes(shared > 0, loc_sim)) + stat_summary(fun.data="mean_cl_boot")
ggplot(d, aes(jaccard, topic_tfidf)) + geom_point(alpha=.5) + scale_x_log10() + scale_y_log10() + stat_smooth(method="loess", data=d[d$shared > 0 & d$topic_tfidf >0,])
#d$jaccard <- log10(d$jaccard)
#d$topic_tfidf <- log10(d$topic_tfidf)

z <- melt(d[,c("topic_tfidf","description_sim","loc_sim","shared_bin")], id.var="shared_bin")
ggplot(z, aes(shared_bin,value))  +  stat_summary(color='red',fun.data="mean_cl_boot") + facet_wrap(~variable,scales="free")

